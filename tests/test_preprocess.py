from pathlib import Path
import pandas as pd
from scripts.prepare_yield_data import normalize

def test_normalize_derives_yield_and_filters_state(tmp_path: Path):
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    pd.DataFrame([
        {"State_Name":"Gujarat", "District_Name":"Rajkot", "Crop_Year":2018, "Season":"Kharif", "Crop":"Groundnut", "Area":2, "Production":4},
        {"State_Name":"Maharashtra", "District_Name":"Pune", "Crop_Year":2018, "Season":"Kharif", "Crop":"Groundnut", "Area":2, "Production":7},
    ]).to_csv(source, index=False)
    frame = normalize(source, output)
    assert len(frame) == 1
    assert frame.iloc[0].yield_tpha == 2
    assert output.exists()

