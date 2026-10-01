import json
from io import BytesIO
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from backend.main import app

client = TestClient(app)

def test_health_reports_bundled_models_ready():
    response = client.get('/api/health')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert body['models'] == {'yield': True, 'leaf_disease': True}

def test_data_insights_are_grounded_in_processed_records():
    response = client.get('/api/insights')
    assert response.status_code == 200
    data = response.json()
    assert data['summary']['records'] == 6974
    assert data['summary']['districts'] == 27
    assert data['crop_medians']
    assert data['model_metrics']['best_model'] == 'Random Forest'

def test_planner_lists_dataset_options_but_disables_unsupported_combinations():
    options = client.get('/api/planner/options').json()
    assert len(options['districts']) == 27
    assert len(options['crops']) == 28
    assert len(options['seasons']) == 4
    assert 'Rajkot' in options['supported_districts']
    assert 'Bulsar' in options['districts']
    assert 'Bulsar' not in options['supported_districts']

def test_yield_prediction_and_return_scenario():
    options = client.get('/api/planner/options').json()
    assert options['data_available'] is True
    combo = options['combinations'][0]
    response = client.post('/api/planner/predict', json={
        **{k: combo[k] for k in ['district', 'crop', 'season']},
        'area_hectares': 2,
        'expected_price_per_tonne': 50000,
        'cost_per_hectare': 30000,
    })
    assert response.status_code == 200
    result = response.json()
    assert result['yield_tonnes_per_hectare'] >= 0
    assert result['estimated_total_tonnes'] == result['yield_tonnes_per_hectare'] * 2
    assert result['estimated_return_inr'] == result['estimated_revenue_inr'] - result['estimated_cost_inr']
    assert result['historical_records'] >= 3

def test_planner_converts_acres_quintals_and_acre_costs_to_canonical_units():
    options = client.get('/api/planner/options').json()
    combo = next(c for c in options['combinations'] if c['district'] == 'Rajkot' and c['crop'] == 'Groundnut' and c['season'] == 'Kharif')
    response = client.post('/api/planner/predict', json={
        **{k: combo[k] for k in ['district', 'crop', 'season']},
        'area_value': 1 / 0.40468564224,
        'area_unit': 'acres',
        'price_value': 5000,
        'price_unit': 'per_quintal',
        'cost_value': 30000 * 0.40468564224,
        'cost_unit': 'per_acre',
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['farm_area_hectares'] == 1
    assert result['price_per_tonne_inr'] == 50000
    assert result['cost_per_hectare_inr'] == 30000
    # The same conversion route also supports per-square-metre cost input.
    request_data = {
        **{k: combo[k] for k in ['district', 'crop', 'season']},
        'area_value': 1,
        'area_unit': 'hectares',
        'price_value': 50000,
        'price_unit': 'per_tonne',
        'cost_value': 3,
        'cost_unit': 'per_square_metre',
    }
    square_metre_response = client.post('/api/planner/predict', json=request_data)
    assert square_metre_response.status_code == 200, square_metre_response.text
    assert square_metre_response.json()['cost_per_hectare_inr'] == 30000

def test_included_planner_example_is_a_valid_api_request():
    with open('data/demo/planner_example.json', encoding='utf-8') as sample:
        payload = json.load(sample)['inputs']
    response = client.post('/api/planner/predict', json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['farm_area_hectares'] > 0

def test_leaf_screening_returns_three_matches_and_focus_map():
    image = Image.new('RGB', (360, 280), '#e8ebda')
    draw = ImageDraw.Draw(image)
    draw.ellipse((92, 34, 275, 253), fill='#4b8c4c', outline='#2f663a', width=4)
    draw.line((115, 210, 250, 82), fill='#d9e6b7', width=5)
    payload = BytesIO()
    image.save(payload, format='JPEG')
    response = client.post('/api/diagnose', files={'file': ('leaf.jpg', payload.getvalue(), 'image/jpeg')})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result['predictions']) == 3
    assert result['focus_map'].startswith('data:image/jpeg;base64,')
    assert 'screening' in result['screening_notice'].lower()

def test_bundled_leaf_demo_image_runs_through_screening_endpoint():
    sample_path = 'public/demo_leaf_spot_pattern.jpg'
    with open(sample_path, 'rb') as sample:
        response = client.post('/api/diagnose', files={'file': ('demo_leaf_spot_pattern.jpg', sample, 'image/jpeg')})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result['predictions']) == 3
    assert result['focus_map'].startswith('data:image/jpeg;base64,')
