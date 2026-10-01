# Leaf classifier attribution

- Model: ConCaPlant plant-leaf image classifier, ONNX export
- Upstream model card: https://huggingface.co/imaflower/plantvillage-mobilenetv3
- License shown on the upstream model card: MIT
- Training dataset named by upstream: PlantVillage
- Output labels: the 15 entries in `disease_labels.json`

This is an upstream pretrained checkpoint included for working inference. It was not trained by FasalScope. Its model card notes the controlled image setting and cautions that field-photo performance may be lower. This app displays model scores and an occlusion-sensitivity overlay as screening aids, not a diagnosis.

If you train a new model with `scripts/train_leaf_model.py`, that script replaces the ONNX file and label map with its own 38-class MobileNetV3-Small outputs. Preserve the training dataset's license and publish the new model's evaluation details before making accuracy claims.

The app also includes a synthetic, AI-generated spot-pattern leaf illustration at `public/demo_leaf_spot_pattern.jpg` for showing the interface flow. It is not part of PlantVillage, not a labeled test image, and not evidence of model accuracy. Its model prediction has no ground-truth label.
