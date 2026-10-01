# FasalScope — Crop Health and Farm Planning

FasalScope is a responsive web app with two distinct data-science features:

1. **Leaf image screening (deep learning):** an ONNX image classifier returns its top match among 15 supported PlantVillage categories, plus an occlusion-sensitivity image to show which areas affected its score.
2. **Crop yield and return planner (classical ML):** a trained scikit-learn regressor estimates a historical yield baseline for supported Gujarat district/crop/season combinations. The app calculates harvest, gross revenue, cost, and estimated return from user-entered area, price, and cost inputs.

It is a decision-support demo. Image screening is not a confirmed diagnosis. Yield and return estimates are not guaranteed harvest or profit.

## Model and data provenance

The **yield model was trained for this project** on 6,974 Gujarat records from the included cleaned government-statistics dataset. It compares Ridge Regression, Random Forest, and Extra Trees with a time-based holdout; the selected pipeline and evaluation results are included in `artifacts/`.

The **leaf classifier is a pretrained model** from the MIT-licensed `imaflower/plantvillage-mobilenetv3` Hugging Face repository. Its ONNX model, external ONNX weights, and label map are bundled so image screening works after deployment. This checkpoint was trained by its upstream author; it is not represented as a model trained by this project. The provided PyTorch script can train a separate MobileNetV3-Small model from PlantVillage images when those source images are available.

The application and trained assets are included in this package. The source image dataset is not bundled. The yield model uses historical records through 2011–12, so treat its result as a **historical baseline for learning and scenario exploration**, not a current-season forecast. It does not use soil or weather inputs.

## Technology stack

- Frontend: React, Vite, responsive CSS, installable PWA, Recharts, Lucide icons
- API: Python, FastAPI, Pydantic, Uvicorn
- ML: pandas, NumPy, scikit-learn pipelines, Ridge baseline, Random Forest and Extra Trees comparison, joblib
- DL: ONNX image classifier for CPU inference; PyTorch/torchvision MobileNetV3-Small training pipeline
- Image handling: Pillow, normalized RGB input, occlusion-sensitivity visualization
- Deployment: Docker, Render Blueprint

## Data sources

### Yield model

Use the Government of Gujarat / OGD crop area and production dataset or the district-wise crop-production statistics resource:

- [Included cleaned India crop dataset](https://github.com/k0rn/India_Agri_Data) — described by its maintainer as cleaned Government of India agriculture data, released under CC0; this project uses the Gujarat rows (1998–99 through 2011–12).
- [Gujarat area, production and yield dataset](https://www.data.gov.in/catalog/area-production-and-yield-major-crops-gujarat-state) and [district-wise crop statistics](https://www.data.gov.in/catalog/district-wise-season-wise-crop-production-statistics-0) are the official references for refreshing the data in a future version.
- [AGMARKNET-derived daily mandi prices](https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi) can inform a user's expected sale price. Current app calculations use the price the user enters.

The bundled raw CSV has district, crop, season, year, area, and production; the preprocessing script filters Gujarat and derives yield as `production / area`. All districts, crops, and seasons found in the processed dataset are listed by the options endpoint; combinations with fewer than three historical records are marked unavailable in the interface.

Prices and cultivation costs are user inputs in the current release. AGMARKNET data can be used to inform a user-entered price in a later iteration; it is not presented as a guaranteed farm-gate price.

### Leaf image model

- [PlantVillage dataset and paper](https://github.com/spMohanty/PlantVillage-Dataset) — image-level classification benchmark, commonly distributed as 38 crop/disease categories.
- [Bundled upstream model card](https://huggingface.co/imaflower/plantvillage-mobilenetv3) — MIT license, 15-class checkpoint and ONNX exports.
- [PlantDoc dataset](https://github.com/pratikkayal/PlantDoc-Dataset) — smaller collection of more natural field-style images. Use it as an external evaluation set only for labels that match the trained classes.

The bundled model covers 15 labels (pepper, potato, and tomato categories). PlantVillage images have a controlled visual setting. Model scores do not establish field accuracy. Retake unclear photos or consult a local agriculture expert; never claim it diagnoses every crop or disease.

## Project layout

```text
fasalscope/
├── backend/main.py                 # FastAPI endpoints and static frontend hosting
├── src/                             # React application and styles
├── data/raw/                        # Included cleaned source CSV and provenance note
├── data/processed/                  # Normalized Gujarat training table
├── data/images/PlantVillage/        # Optional source images for retraining (not included)
├── artifacts/                       # Yield model, metrics, ONNX model and labels
├── scripts/prepare_yield_data.py
├── scripts/train_yield_model.py
├── scripts/train_leaf_model.py
├── Dockerfile
└── render.yaml
```

## Train the ML model

1. Create a Python 3.11 environment and install the training requirements.

   ```bash
   python -m venv .venv
   # Windows Command Prompt
   .venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -r requirements-training.txt
   ```

2. The source CSV is already included. Normalize it and train/evaluate the candidate regressors:

   ```bash
   python scripts/prepare_yield_data.py
   python scripts/train_yield_model.py
   ```

The evaluation holds out the latest 20% of years. It compares Ridge Regression, Random Forest, and Extra Trees using MAE, RMSE, and R², then saves the selected model as `artifacts/yield_model.joblib` and metrics to `artifacts/yield_metrics.json`. On the bundled historical data, Random Forest scored MAE 1.58 tonnes/hectare, RMSE 5.91 tonnes/hectare, and R² 0.630 on 2009–2011 (1,776 test rows). Training stops if the available history is too small for a meaningful time-based split. These results describe this old data window and should not be treated as current-season accuracy.

## Train the DL model

Place the extracted PlantVillage class folders under `data/images/PlantVillage/`, for example:

```text
data/images/PlantVillage/
├── Apple___Apple_scab/
│   ├── image_1.jpg
│   └── ...
└── Apple___healthy/
    └── ...
```

Train and export the ONNX model:

```bash
python scripts/train_leaf_model.py --epochs 5
```

This saves `artifacts/model.onnx`, `artifacts/disease_labels.json`, `artifacts/disease_metrics.json`, and a PyTorch checkpoint. It replaces the bundled upstream 15-class ONNX checkpoint with a 38-class model trained from the provided images. Training uses class-stratified image splits; because related images may still share visual characteristics, this is a benchmark result, not proof of performance on independently collected farms. Test matching PlantDoc classes before making stronger claims.

The training script starts from torchvision's MobileNetV3-Small weights, so the first training run downloads those weights. A GPU speeds up training but is not required. The bundled ONNX checkpoint is a separate upstream model; see `artifacts/MODEL_ATTRIBUTION.md`.

## Run locally

Open two VS Code terminals in the project folder.

**Terminal 1 — API**

```bash
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — frontend**

```bash
npm install
npm run dev
```

Open the URL printed by Vite (usually `http://localhost:5173`). API docs are at `http://localhost:8000/docs`; health status is at `http://localhost:8000/api/health`.

## Deploy on Render

The included `render.yaml` and `Dockerfile` run the built React frontend and FastAPI API from one web service. Confirm that `artifacts/yield_model.joblib`, `artifacts/model.onnx`, `artifacts/model.onnx.data`, and `artifacts/disease_labels.json` are present and that `/api/health` reports both models available. Push the project to your GitHub repository, then create a Render Blueprint from that repository and deploy the `fasalscope` service. The service may sleep on a free plan and can take time to wake.

For local Docker verification after training:

```bash
docker build -t fasalscope .
docker run --rm -p 8000:8000 fasalscope
```

Open `http://localhost:8000`. The same service serves both the frontend and API, so no separate frontend API URL is needed.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | API and model readiness |
| GET | `/api/planner/options` | Crop, district, and season options from processed data |
| GET | `/api/insights` | Dataset summary, district crop medians, and model evaluation |
| POST | `/api/planner/predict` | Yield estimate plus user-input return scenario |
| POST | `/api/diagnose` | Leaf-image top-three classification |

## Model evaluation and interpretation

- **Regression:** MAE and RMSE are in tonnes per hectare; R² is reported for context. A lower MAE/RMSE is better. Split by year to test forward-in-time generalization.
- **Image classification:** the bundled upstream checkpoint provides top-3 softmax scores; these are relative model scores, not calibrated probabilities. The occlusion map is a model-inspection aid. Retraining with the included script writes per-class precision, recall, and F1 to `disease_metrics.json`.
- Predictions only cover categories present in the model's labels. Unsupported crops can still receive a wrong top match, so seek local expert advice before treatment.

## Known scope limits

- Yield estimation uses old records from 1998–2011; it is a learning baseline, not current guidance for planting decisions. The model does not infer yield from soil test results or forecast weather.
- Return is an arithmetic scenario based on user-entered sale price and cost, not a learned profit prediction.
- Image predictions cover only the trained classes. PlantVillage-to-field domain shift can reduce performance.
- This is an educational decision-support project, not agronomic, pesticide, or financial advice.

## Guided demo inputs

The planner's dropdowns are populated from `data/processed/gujarat_crop_history.csv` through `GET /api/planner/options`; you do not need to import a separate crop-options file. It lists every district, crop, and season found in that processed dataset. Dropdown choices with fewer than three matching historical records are disabled, so every selectable district/crop/season combination is supported by the trained model. This includes all dataset values while preventing unsupported combinations from producing failed predictions.

Choose **Fill example** in the planner to load Rajkot / Groundnut / Kharif with an illustrative 2-acre area, ₹5,500 per quintal, and ₹32,000 per hectare cost scenario. These values are for demonstrating the interface only; they are not live mandi prices or cost recommendations. The equivalent request example is in `data/demo/planner_example.json`.

Area inputs accept hectares, acres, guntha, or square metres. Selling price accepts rupees per tonne, quintal, or kilogram. Cultivation cost accepts rupees per hectare, acre, guntha, or square metre. The API normalizes all inputs to hectares and rupees per tonne/per hectare before applying the model and arithmetic return calculation.

On **Crop health check**, choose **Load sample leaf** to load `public/demo_leaf_spot_pattern.jpg`. This is a synthetic demonstration image, not a PlantVillage test example or real field photo. It lets you show the complete upload → model screening → top matches → occlusion map flow; do not use its result as model validation evidence. The model is trained for supported pepper, potato, and tomato label categories only.
