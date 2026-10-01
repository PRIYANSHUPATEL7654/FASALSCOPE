"""Normalize a district crop production CSV into the FasalScope training schema."""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ALIASES = {
    "state": ["state", "state_name", "statename"],
    "district": ["district", "district_name", "districtname"],
    "year": ["year", "crop_year", "cropyear"],
    "season": ["season"],
    "crop": ["crop", "crop_name", "cropname"],
    "area": ["area", "area_ha", "area_hectare", "area_hectares"],
    "production": ["production", "production_tonnes", "production_tons"],
}

def key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def normalize(source: Path, output: Path) -> pd.DataFrame:
    raw = pd.read_csv(source, low_memory=False)
    lookup = {key(c): c for c in raw.columns}
    found = {}
    for target, candidates in ALIASES.items():
        col = next((lookup[key(c)] for c in candidates if key(c) in lookup), None)
        if col is None and target != "state":
            raise ValueError(f"Could not find the '{target}' field. CSV columns: {list(raw.columns)}")
        found[target] = col
    selected = {target: raw[col] if col else pd.Series("gujarat", index=raw.index) for target, col in found.items()}
    df = pd.DataFrame(selected)
    if found["state"]:
        df["state"] = df["state"].astype(str).str.strip().str.lower()
        df = df[df["state"].isin(["gujarat", "gujrat"])].copy()
    df["year"] = pd.to_numeric(df["year"].astype(str).str.extract(r"(\d{4})", expand=False), errors="coerce")
    for c in ["area", "production"]:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    for c in ["district", "season", "crop"]:
        df[c] = df[c].astype(str).str.strip().str.title()
    df = df.dropna(subset=["district", "crop", "season", "year", "area", "production"])
    df = df[(df["area"] > 0) & (df["production"] >= 0)]
    df["yield_tpha"] = df["production"] / df["area"]
    df = df.replace([float("inf"), -float("inf")], pd.NA).dropna(subset=["yield_tpha"])
    # Keep credible records; the 99.5th percentile cap is fit per crop to reduce unit errors.
    cutoff = df.groupby("crop")["yield_tpha"].transform(lambda x: x.quantile(.995))
    df = df[df["yield_tpha"] <= cutoff]
    output.parent.mkdir(parents=True, exist_ok=True)
    df[["district", "crop", "season", "year", "yield_tpha", "area", "production"]].to_csv(output, index=False)
    return df

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", nargs="?", default=str(ROOT / "data/raw/india_agriculture_cleaned.csv"))
    p.add_argument("--output", default=str(ROOT / "data/processed/gujarat_crop_history.csv"))
    args = p.parse_args()
    frame = normalize(Path(args.source), Path(args.output))
    print(f"Saved {len(frame):,} Gujarat crop records to {args.output}")
