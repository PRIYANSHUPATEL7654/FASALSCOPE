#!/usr/bin/env sh
set -eu
python scripts/prepare_yield_data.py
python scripts/train_yield_model.py
python scripts/train_leaf_model.py

