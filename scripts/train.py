"""
MINT Training Script — Fine-tune Qwen2.5-Coder-7B on MuleSoft code.

Uses Unsloth MLXTrainer for fast LoRA training on Mac.

Usage:
    python scripts/train.py --test       # Quick test (10 examples, 20 steps)
    python scripts/train.py              # Full training
"""

import argparse
import json
from pathlib import Path


def load_training_data(path: str, max_samples: int = None):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
            if max_samples and len(data) >= max_samples:
                break
    return data


def format_for_training(examples):
    formatted = []
    for ex in examples:
        formatted.append({
            "messages": [
                {"role": "system", "content": "You are MINT, an expert MuleSoft developer. Generate complete, valid Mule 4 XML flows and DataWeave transformations."},
                {"role": "user", "content": ex["instruction"]},
                {"role": "assistant", "content": ex["output"]},
            ]
        })
    return formatted


def train(args):
    from unsloth import FastLanguageModel, MLXTrainer, MLXTrainingConfig
    from datasets import Dataset

    print("=" * 60)
    print("MINT Training (MLX on Mac)")
    print("=" * 60)

    # Load data
    print("[1/4] Loading training data...")
    max_samples = 10 if args.test else None
    raw_data = load_training_data(args.data, max_samples=max_samples)
    formatted = format_for_training(raw_data)
    dataset = Dataset.from_list(formatted)
    print(f"  Loaded {len(dataset)} examples")

    # Load model
    print("\n[2/4] Loading Qwen2.5-Coder-7B-Instruct...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="Qwen/Qwen2.5-Coder-7B-Instruct",
        max_seq_length=4096,
        dtype=None,
        load_in_4bit=True,
    )

    # Add LoRA
    print("\n[3/4] Adding LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    # Format dataset
    def apply_chat_template(examples):
        texts = []
        for messages in examples["messages"]:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            texts.append(text)
        return {"text": texts}

    dataset = dataset.map(apply_chat_template, batched=True)

    # Train
    output_dir = str(Path(args.output) / ("test_run" if args.test else "mint-lora"))
    print(f"\n[4/4] Training → {output_dir}")

    config = MLXTrainingConfig(
        output_dir=output_dir,
        max_steps=20 if args.test else -1,
        num_train_epochs=1 if args.test else 3,
        logging_steps=5,
        save_steps=20 if args.test else 100,
        learning_rate=2e-4,
        per_device_train_batch_size=1,
    )

    trainer = MLXTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=config,
        dataset_text_field="text",
    )

    trainer.train()

    print(f"\n✓ Training complete! Model saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="MINT Training")
    parser.add_argument("--data", default="data/training.jsonl")
    parser.add_argument("--output", default="models/")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
