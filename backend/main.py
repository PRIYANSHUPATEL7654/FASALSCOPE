from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
DATA = ROOT / "data"
FRONTEND = ROOT / "frontend" / "dist"

app = FastAPI(title="FasalScope API", version="1.0.0", description="Crop health screening and farm planning")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

yield_bundle: dict[str, Any] | None = None
disease_session = None
disease_labels: list[str] | None = None
yield_data_path = DATA / "processed" / "gujarat_crop_history.csv"


class PlannerRequest(BaseModel):
    district: str
    crop: str
    season: str
    area_value: float | None = Field(default=None, gt=0, le=1_000_000)
    area_unit: Literal["hectares", "acres", "guntha", "square_metres"] = "hectares"
    price_value: float | None = Field(default=None, ge=0, le=10_000_000)
    price_unit: Literal["per_tonne", "per_quintal", "per_kg"] = "per_tonne"
    cost_value: float | None = Field(default=None, ge=0, le=10_000_000)
    cost_unit: Literal["per_hectare", "per_acre", "per_guntha", "per_square_metre"] = "per_hectare"
    # Legacy canonical fields remain accepted for existing API clients.
    area_hectares: float | None = Field(default=None, gt=0, le=10000)
    expected_price_per_tonne: float | None = Field(default=None, ge=0, le=10_000_000)
    cost_per_hectare: float | None = Field(default=None, ge=0, le=10_000_000)

    @model_validator(mode="after")
    def require_planner_values(self):
        if self.area_value is None and self.area_hectares is None:
            raise ValueError("Provide area_value or area_hectares.")
        if self.price_value is None and self.expected_price_per_tonne is None:
            raise ValueError("Provide price_value or expected_price_per_tonne.")
        if self.cost_value is None and self.cost_per_hectare is None:
            raise ValueError("Provide cost_value or cost_per_hectare.")
        return self


def load_yield_bundle() -> dict[str, Any] | None:
    path = ARTIFACTS / "yield_model.joblib"
    if not path.exists():
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


def get_yield_bundle() -> dict[str, Any] | None:
    global yield_bundle
    if yield_bundle is None:
        yield_bundle = load_yield_bundle()
    return yield_bundle


def get_disease_model():
    global disease_session, disease_labels
    model_path = ARTIFACTS / "model.onnx"
    labels_path = ARTIFACTS / "disease_labels.json"
    if disease_session is None:
        import onnxruntime as ort
        disease_session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    if disease_labels is None:
        disease_labels = json.loads(labels_path.read_text())
    return disease_session, disease_labels


@app.get("/api/health")
def health() -> dict[str, Any]:
    bundle = get_yield_bundle()
    disease_ready = all((ARTIFACTS / name).exists() for name in ["model.onnx", "model.onnx.data", "disease_labels.json"])
    return {
        "status": "ok",
        "app": "FasalScope",
        "models": {"yield": bundle is not None, "leaf_disease": disease_ready},
        "message": "Ready" if bundle and disease_ready else "Application is running; check model status before relying on predictions.",
    }


@app.get("/api/planner/options")
def planner_options() -> dict[str, Any]:
    if not yield_data_path.exists():
        return {"districts": [], "crops": [], "seasons": [], "supported_districts": [], "combinations": [], "data_available": False}
    df = pd.read_csv(yield_data_path)
    combos = df.groupby(["district", "crop", "season"]).size().reset_index(name="records")
    combos = combos[combos.records >= 3]
    return {
        "districts": sorted(df["district"].dropna().astype(str).unique().tolist()),
        "crops": sorted(df["crop"].dropna().astype(str).unique().tolist()),
        "seasons": sorted(df["season"].dropna().astype(str).unique().tolist()),
        "supported_districts": sorted(combos["district"].dropna().astype(str).unique().tolist()),
        "combinations": combos.to_dict(orient="records"),
        "data_available": not combos.empty,
    }


@app.get("/api/insights")
def data_insights(district: str | None = None) -> dict[str, Any]:
    if not yield_data_path.exists():
        raise HTTPException(status_code=503, detail="Processed crop history is not available.")
    df = pd.read_csv(yield_data_path)
    if district and district in set(df.district.astype(str)):
        df = df[df.district.astype(str) == district]
    summary = {
        "records": int(len(df)),
        "districts": int(df.district.nunique()),
        "crops": int(df.crop.nunique()),
        "first_year": int(df.year.min()),
        "last_year": int(df.year.max()),
        "selected_district": district or "All Gujarat",
    }
    grouped = df.groupby("crop").yield_tpha.agg(["median", "count"]).reset_index()
    grouped = grouped.sort_values("median", ascending=False).head(10)
    metrics_path = ARTIFACTS / "yield_metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else None
    return {
        "summary": summary,
        "district_options": sorted(pd.read_csv(yield_data_path, usecols=["district"]).district.dropna().astype(str).unique().tolist()),
        "crop_medians": [{"crop": str(r.crop), "median_yield": round(float(r.median), 2), "records": int(r.count)} for r in grouped.itertuples(index=False)],
        "model_metrics": metrics,
        "note": "Historical median yield is a descriptive statistic, not a crop suitability recommendation. The source data ends in 2011–12.",
    }


@app.post("/api/planner/predict")
def predict_yield(body: PlannerRequest) -> dict[str, Any]:
    bundle = get_yield_bundle()
    if not bundle:
        raise HTTPException(status_code=503, detail="Yield model is not available. Follow the model setup in README.md.")
    model = bundle["pipeline"]
    combo_key = f"{body.district}|{body.crop}|{body.season}"
    historical = bundle.get("historical", {}).get(combo_key)
    if not historical or historical.get("count", 0) < 3:
        raise HTTPException(status_code=422, detail="There are not enough historical records for this district, crop, and season combination.")

    area_to_hectares = {"hectares": 1.0, "acres": 0.40468564224, "guntha": 0.010117141056, "square_metres": 0.0001}
    price_to_tonne = {"per_tonne": 1.0, "per_quintal": 10.0, "per_kg": 1000.0}
    cost_area_to_hectares = {"per_hectare": 1.0, "per_acre": 0.40468564224, "per_guntha": 0.010117141056, "per_square_metre": 0.0001}
    area_value = body.area_value if body.area_value is not None else body.area_hectares
    price_value = body.price_value if body.price_value is not None else body.expected_price_per_tonne
    cost_value = body.cost_value if body.cost_value is not None else body.cost_per_hectare
    area_unit = body.area_unit if body.area_value is not None else "hectares"
    price_unit = body.price_unit if body.price_value is not None else "per_tonne"
    cost_unit = body.cost_unit if body.cost_value is not None else "per_hectare"
    area_hectares = float(area_value) * area_to_hectares[area_unit]
    expected_price_per_tonne = float(price_value) * price_to_tonne[price_unit]
    cost_per_hectare = float(cost_value) / cost_area_to_hectares[cost_unit]
    if area_hectares > 10000 or expected_price_per_tonne > 10_000_000 or cost_per_hectare > 10_000_000:
        raise HTTPException(status_code=422, detail="Converted area, price, or cost is above the supported limit. Check the selected unit.")
    record = pd.DataFrame([{
        "district": body.district,
        "crop": body.crop,
        "season": body.season,
    }])
    try:
        yld = max(0.0, float(model.predict(record)[0]))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not estimate this crop combination: {exc}") from exc
    total_tonnes = yld * area_hectares
    revenue = total_tonnes * expected_price_per_tonne
    cost = cost_per_hectare * area_hectares
    return {
        "yield_tonnes_per_hectare": round(yld, 2),
        "estimated_total_tonnes": round(total_tonnes, 2),
        "estimated_revenue_inr": round(revenue, 2),
        "estimated_cost_inr": round(cost, 2),
        "estimated_return_inr": round(revenue - cost, 2),
        "farm_area_hectares": round(area_hectares, 4),
        "price_per_tonne_inr": round(expected_price_per_tonne, 2),
        "cost_per_hectare_inr": round(cost_per_hectare, 2),
        "historical_average": historical.get("mean"),
        "historical_records": historical.get("count"),
        "model": bundle.get("model_name", "scikit-learn regressor"),
        "note": "Historical baseline from Gujarat district, crop, and season records (1998–2011). It does not include current weather or soil readings and is not a forecast guarantee.",
    }


@app.post("/api/diagnose")
async def diagnose_leaf(file: UploadFile = File(...)) -> dict[str, Any]:
    path = ARTIFACTS / "model.onnx"
    labels_path = ARTIFACTS / "disease_labels.json"
    if not path.exists() or not labels_path.exists():
        raise HTTPException(status_code=503, detail="Leaf model is not available. Follow the model setup in README.md.")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WEBP leaf image.")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be smaller than 8 MB.")
    try:
        from PIL import Image, ImageOps
        from io import BytesIO
        image = Image.open(BytesIO(data)).convert("RGB")
        session, labels = get_disease_model()
        input_info = session.get_inputs()[0]
        shape = input_info.shape
        image_size = shape[-1] if isinstance(shape[-1], int) else 256
        image = ImageOps.fit(image, (image_size, image_size), method=Image.Resampling.LANCZOS)
        x = np.asarray(image, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        x = ((x - mean) / std).transpose(2, 0, 1)[None, ...].astype(np.float32)
        output = session.run(None, {input_info.name: x})[0]
        logits = output[0]
        probs = np.exp(logits - np.max(logits))
        probs = probs / probs.sum()
        order = np.argsort(probs)[::-1][:3]
        # Occlusion sensitivity: measure how covering each image patch changes the top-class score.
        grid = 8
        patch = max(1, image_size // grid)
        masked = np.repeat(x, grid * grid, axis=0)
        for idx in range(grid * grid):
            row, col = divmod(idx, grid)
            masked[idx, :, row*patch:min((row+1)*patch,image_size), col*patch:min((col+1)*patch,image_size)] = 0.0
        mask_logits = session.run(None, {input_info.name: masked})[0]
        mask_logits = mask_logits - mask_logits.max(axis=1, keepdims=True)
        mask_probs = np.exp(mask_logits); mask_probs /= mask_probs.sum(axis=1, keepdims=True)
        sensitivity = np.maximum(0, float(probs[int(order[0])]) - mask_probs[:, int(order[0])]).reshape(grid, grid)
        if sensitivity.max() > 0:
            sensitivity = sensitivity / sensitivity.max()
        heat = Image.fromarray(np.uint8(sensitivity * 255)).resize((image_size,image_size), Image.Resampling.BICUBIC)
        heat_np = np.asarray(heat, dtype=np.float32) / 255.0
        original = np.asarray(image, dtype=np.float32)
        colors = np.stack([255*heat_np, 255*(1-np.abs(heat_np-.5)*2), 255*(1-heat_np)], axis=-1)
        overlay = np.uint8(np.clip(original*.56 + colors*.44, 0, 255))
        from base64 import b64encode
        from io import BytesIO
        buffer = BytesIO(); Image.fromarray(overlay).save(buffer, format="JPEG", quality=82)
        focus_map = "data:image/jpeg;base64," + b64encode(buffer.getvalue()).decode("ascii")
        return {"predictions": [{"label": labels[int(i)], "confidence": round(float(probs[i]), 4)} for i in order], "focus_map": focus_map, "explanation": "Color overlay shows image patches that changed the top prediction score when covered. It is a model-inspection aid, not a disease boundary.", "screening_notice": "This is an image-based screening result, not a confirmed diagnosis. Consult a local agriculture expert before treatment."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process this image: {exc}") from exc


if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def frontend(full_path: str):
        candidate = FRONTEND / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND / "index.html")
