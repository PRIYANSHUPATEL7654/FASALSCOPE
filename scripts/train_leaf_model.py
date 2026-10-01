"""Fine-tune MobileNetV3-Small on an ImageFolder dataset and export ONNX.

Expected layout: data/images/PlantVillage/<class_name>/<image files>
The image dataset is intentionally not copied into this repository.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import torch
from torch import nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms, models
from sklearn.metrics import accuracy_score, classification_report

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data/images/PlantVillage"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit-per-class", type=int, default=0, help="Optional quick experiment cap; 0 uses the full dataset")
    args = parser.parse_args()
    data_root = Path(args.data)
    if not data_root.exists():
        raise SystemExit(f"Dataset folder not found: {data_root}. See README.md for dataset source and layout.")
    torch.manual_seed(42)
    train_transform = transforms.Compose([
        transforms.Resize((232, 232)), transforms.RandomResizedCrop(224, scale=(.72, 1.0)),
        transforms.RandomHorizontalFlip(), transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=.14, contrast=.14, saturation=.12),
        transforms.ToTensor(), transforms.Normalize([.485,.456,.406],[.229,.224,.225]),
    ])
    eval_transform = transforms.Compose([transforms.Resize((224,224)), transforms.ToTensor(), transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    base = datasets.ImageFolder(data_root, transform=train_transform)
    if len(base.classes) < 2 or len(base) < 200:
        raise SystemExit("Expected at least 2 classes and 200 images. Check the dataset folder structure.")
    classes = base.classes
    # Deterministic stratification keeps class proportions in train and validation.
    labels = torch.tensor(base.targets)
    train_idx, val_idx = [], []
    generator = torch.Generator().manual_seed(42)
    for class_id in range(len(classes)):
        idx = torch.where(labels == class_id)[0]
        idx = idx[torch.randperm(len(idx), generator=generator)]
        cut = max(1, int(len(idx) * .2))
        val_idx.extend(idx[:cut].tolist()); train_idx.extend(idx[cut:].tolist())
    train_set = torch.utils.data.Subset(base, train_idx)
    val_base = datasets.ImageFolder(data_root, transform=eval_transform)
    val_set = torch.utils.data.Subset(val_base, val_idx)
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False, num_workers=2)
    weights = models.MobileNet_V3_Small_Weights.DEFAULT
    model = models.mobilenet_v3_small(weights=weights)
    for p in model.features.parameters(): p.requires_grad = False
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(classes))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss()
    for epoch in range(args.epochs):
        model.train(); total_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True); loss = loss_fn(model(x), y); loss.backward(); optimizer.step()
            total_loss += loss.item() * len(y)
        print(f"Epoch {epoch+1}/{args.epochs} — train loss {total_loss / len(train_set):.4f}")
    model.eval(); truth, pred = [], []
    with torch.no_grad():
        for x, y in val_loader:
            out = model(x.to(device)).argmax(1).cpu().tolist()
            truth.extend(y.tolist()); pred.extend(out)
    report = classification_report(truth, pred, target_names=classes, output_dict=True, zero_division=0)
    out_dir = ROOT / "artifacts"; out_dir.mkdir(exist_ok=True)
    torch.save({"state_dict": model.cpu().state_dict(), "classes": classes}, out_dir / "disease_model.pt")
    (out_dir / "disease_labels.json").write_text(json.dumps(classes, indent=2))
    (out_dir / "disease_metrics.json").write_text(json.dumps({"accuracy": accuracy_score(truth,pred), "report": report, "classes": classes}, indent=2))
    # ONNX is the small CPU inference artifact used by the FastAPI deployment.
    dummy = torch.randn(1, 3, 224, 224)
    torch.onnx.export(model, dummy, out_dir / "model.onnx", input_names=["image"], output_names=["logits"], dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}}, opset_version=17)
    print(f"Validation accuracy: {accuracy_score(truth,pred):.3f}")
    print(f"Saved ONNX model and metrics to {out_dir}")

if __name__ == "__main__": main()
