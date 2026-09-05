"""
Fine-tune distilbert-base-uncased for binary prompt complexity classification.

Usage:
    python training/train_distilbert.py

Reads:   training/data/labeled_dataset.json
Saves:   training/model/distilbert-complexity/

The trained model classifies prompts as:
  - label 0 = "weak"  (cheap model is sufficient)
  - label 1 = "strong" (needs expensive model)

Requirements:
    pip install transformers datasets accelerate scikit-learn
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

import numpy as np
from datasets import Dataset, DatasetDict
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

# ---- Paths ----
HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "data" / "labeled_dataset.json"
OUTPUT_DIR = HERE / "model" / "distilbert-complexity"

# ---- Config ----
BASE_MODEL = "distilbert-base-uncased"
MAX_LENGTH = 512
EPOCHS = 10
BATCH_SIZE = 8
LEARNING_RATE = 1e-5
WARMUP_STEPS = 0.1
WEIGHT_DECAY = 0.01
TRAIN_SPLIT = 0.80  # 80% train, 20% validation
SEED = 42

LABEL2ID = {"weak": 0, "strong": 1}
ID2LABEL = {0: "weak", 1: "strong"}


def load_data() -> DatasetDict:
    """Load the labeled dataset and split into train/val."""
    if not DATA_FILE.exists():
        print(f"[fatal] training data not found: {DATA_FILE}")
        print("        Run `python training/merge_labels.py` first.")
        sys.exit(1)

    with DATA_FILE.open("r", encoding="utf-8") as f:
        items = json.load(f)

    # Convert to HuggingFace Dataset
    texts = [item["prompt"] for item in items]
    labels = [LABEL2ID[item["label"]] for item in items]

    ds = Dataset.from_dict({"text": texts, "label": labels})
    splits = ds.train_test_split(test_size=1 - TRAIN_SPLIT, seed=SEED, stratify_by_column="label")

    print(f"[data] total: {len(ds)}, train: {len(splits['train'])}, val: {len(splits['test'])}")
    print(f"[data] class distribution (train):")
    train_labels = splits["train"]["label"]
    print(f"       weak:   {train_labels.count(0)}")
    print(f"       strong: {train_labels.count(1)}")

    return DatasetDict({"train": splits["train"], "validation": splits["test"]})


def compute_metrics(eval_pred):
    """Compute accuracy and macro F1 for the Trainer."""
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
        "f1_weak": f1_score(labels, preds, pos_label=0),
        "f1_strong": f1_score(labels, preds, pos_label=1),
    }


def main():
    print(f"[model] base: {BASE_MODEL}")
    print(f"[model] output: {OUTPUT_DIR}")

    # ---- Load data ----
    dataset = load_data()

    # ---- Tokenizer ----
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tokenize(examples):
        return tokenizer(
            examples["text"],
            padding=False,  # DataCollator handles padding
            truncation=True,
            max_length=MAX_LENGTH,
        )

    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    # ---- Model ----
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=2,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    # ---- Training args ----
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR / "checkpoints"),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=LEARNING_RATE,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        warmup_steps=WARMUP_STEPS,
        weight_decay=WEIGHT_DECAY,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_dir=str(OUTPUT_DIR / "logs"),
        logging_steps=10,
        seed=SEED,
        fp16=False,  
        report_to="none",  # no wandb/mlflow
        disable_tqdm=False, # explicitly force progress bars
    )

    # ---- Trainer ----
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        processing_class=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    # ---- Train ----
    print("\n" + "=" * 60)
    print("STARTING TRAINING")
    print("=" * 60)
    trainer.train()

    # ---- Evaluate ----
    print("\n" + "=" * 60)
    print("FINAL EVALUATION")
    print("=" * 60)
    results = trainer.evaluate()
    for k, v in results.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    # ---- Detailed classification report ----
    preds_output = trainer.predict(tokenized["validation"])
    preds = np.argmax(preds_output.predictions, axis=-1)
    labels = preds_output.label_ids

    print("\n[Classification Report]")
    print(classification_report(labels, preds, target_names=["weak", "strong"]))

    print("[Confusion Matrix]")
    cm = confusion_matrix(labels, preds)
    print(f"              Predicted")
    print(f"              weak  strong")
    print(f"  Actual weak   {cm[0][0]:4d}  {cm[0][1]:4d}")
    print(f"  Actual strong {cm[1][0]:4d}  {cm[1][1]:4d}")

    # ---- Save final model ----
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print(f"\n[saved] model + tokenizer → {OUTPUT_DIR}")

    # ---- Save label mapping ----
    label_map = {"label2id": LABEL2ID, "id2label": ID2LABEL}
    label_map_file = OUTPUT_DIR / "label_map.json"
    with label_map_file.open("w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)
    print(f"[saved] label map → {label_map_file}")

    print("\n✅ Training complete! The model is ready to use.")
    print(f"   Model path: {OUTPUT_DIR}")
    print(f"   Restart the server and classifier.py will auto-detect it.")


if __name__ == "__main__":
    main()
