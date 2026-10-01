"""Train and evaluate a district/season crop-yield regressor."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/processed/gujarat_crop_history.csv"
ARTIFACTS = ROOT / "artifacts"
FEATURES = ["district", "crop", "season"]
CATEGORICAL = ["district", "crop", "season"]

def main():
    if not INPUT.exists():
        raise SystemExit(f"Missing {INPUT}. First download a suitable official Gujarat APY CSV and run scripts/prepare_yield_data.py.")
    df = pd.read_csv(INPUT)
    df = df.dropna(subset=FEATURES + ["yield_tpha"])
    years = sorted(df.year.unique())
    if len(years) < 5 or len(df) < 100:
        raise SystemExit(f"Need at least 5 distinct years and 100 valid records; found {len(years)} years and {len(df)} rows. Do not train on an undersized sample.")
    test_years = years[-max(1, int(np.ceil(len(years) * .2))):]
    train = df[~df.year.isin(test_years)].copy()
    test = df[df.year.isin(test_years)].copy()
    if train.empty or test.empty:
        raise SystemExit("Unable to create year-based holdout split.")
    pre = ColumnTransformer([
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
    ])
    candidates = {
        "Ridge Regression": Ridge(alpha=1.0),
        "Random Forest": RandomForestRegressor(n_estimators=350, min_samples_leaf=2, max_features=.9, random_state=42, n_jobs=-1),
        "Extra Trees": ExtraTreesRegressor(n_estimators=350, min_samples_leaf=2, max_features=.9, random_state=42, n_jobs=-1),
    }
    rows, pipelines = [], {}
    for name, estimator in candidates.items():
        pipe = TransformedTargetRegressor(
            regressor=Pipeline([("prep", pre), ("model", estimator)]),
            func=np.log1p, inverse_func=np.expm1,
        )
        pipe.fit(train[FEATURES], train.yield_tpha)
        pred = np.maximum(pipe.predict(test[FEATURES]), 0)
        rows.append({"model": name, "mae": mean_absolute_error(test.yield_tpha, pred), "rmse": mean_squared_error(test.yield_tpha, pred) ** .5, "r2": r2_score(test.yield_tpha, pred)})
        pipelines[name] = pipe
        # Each candidate receives its own cloned preprocessing pipeline through sklearn Pipeline.fit.
    metrics = pd.DataFrame(rows).sort_values("mae").reset_index(drop=True)
    best_name = str(metrics.iloc[0].model)
    best = TransformedTargetRegressor(
        regressor=Pipeline([("prep", pre), ("model", candidates[best_name])]),
        func=np.log1p, inverse_func=np.expm1,
    )
    best.fit(df[FEATURES], df.yield_tpha)
    grouped = df.groupby(["district", "crop", "season"]).yield_tpha.agg(["mean", "count"]).round(3)
    historical = {"|".join(map(str, k)): {"mean": float(row["mean"]), "count": int(row["count"])} for k, row in grouped.iterrows()}
    ARTIFACTS.mkdir(exist_ok=True)
    joblib.dump({"pipeline": best, "model_name": best_name, "historical": historical, "feature_names": FEATURES, "source_years": [int(min(years)), int(max(years))], "source_rows": int(len(df))}, ARTIFACTS / "yield_model.joblib")
    metrics.to_csv(ARTIFACTS / "yield_model_comparison.csv", index=False)
    (ARTIFACTS / "yield_metrics.json").write_text(json.dumps({"best_model": best_name, "test_years": [str(y) for y in test_years], "train_rows": len(train), "test_rows": len(test), "results": rows, "feature_names": FEATURES}, indent=2))
    print(metrics.to_string(index=False))
    print(f"\nSaved model: {ARTIFACTS / 'yield_model.joblib'}")

if __name__ == "__main__":
    main()
