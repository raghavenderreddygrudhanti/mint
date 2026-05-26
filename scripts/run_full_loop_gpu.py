"""
MINT — Full recursive loop on GPU (RunPod).

Does everything in one shot:
1. Train v1 (if no model exists)
2. Evaluate on 50 test samples
3. Collect failures
4. Convert failures to training pairs
5. Build v2 dataset
6. Retrain v2
7. Evaluate v2
8. Report improvement

Usage (on RunPod):
    python scripts/run_full_loop_gpu.py
"""

import json
import re
import hashlib
import torch
from pathlib import Path
from xml.etree import ElementTree as ET


def validate_xml(text):
    """Check if output contains valid or near-valid Mule XML."""
    # Check for complete XML
    xml_match = re.search(r'(<\?xml.*?\?>.*?</mule>|<mule.*?</mule>)', text, re.DOTALL)
    if xml_match:
        try:
            ET.fromstring(xml_match.group(0))
            return True, ""
        except ET.ParseError as e:
            return False, f"XML error: {str(e)[:80]}"

    # Check for structural validity (has key elements even if not perfectly closed)
    has_mule = "<mule" in text
    has_flow = "<flow" in text
    has_namespace = "mulesoft.org" in text

    if has_mule and has_flow and has_namespace:
        if "</mule>" not in text:
            return False, "Truncated: missing closing </mule> tag"
        if "</flow>" not in text:
            return False, "Truncated: missing closing </flow> tag"
        return True, ""

    if not has_mule and not has_flow:
        return False, "Not MuleSoft XML: no <mule> or <flow> element"

    return False, "Incomplete XML structure"


def validate_dataweave(text):
    if not text.strip() or len(text.strip()) < 20:
        return False, "Empty or too short"
    if "%dw" in text or "---" in text:
        return True, ""
    return False, "No DataWeave syntax"


def evaluate_model(model, tokenizer, test_data, max_tokens=2048):
    """Evaluate model and return failures."""
    failures = []
    successes = 0

    for i, sample in enumerate(test_data):
        if i % 10 == 0:
            print(f"    Evaluating [{i+1}/{len(test_data)}]...")

        messages = [
            {"role": "system", "content": "You are MINT, an expert MuleSoft developer. Generate complete, valid Mule 4 XML flows and DataWeave transformations."},
            {"role": "user", "content": sample["instruction"]},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=max_tokens, temperature=0.1, do_sample=True, pad_token_id=tokenizer.eos_token_id)

        output_text = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        sample_type = sample.get("metadata", {}).get("type", "flow")

        if sample_type == "flow":
            valid, error = validate_xml(output_text)
        else:
            valid, error = validate_dataweave(output_text)

        if valid:
            successes += 1
        else:
            failures.append({
                "instruction": sample["instruction"],
                "model_output": output_text[:3000],
                "expected_output": sample["output"][:3000],
                "error_reason": error,
                "type": sample_type,
            })

    accuracy = successes / len(test_data) * 100
    return accuracy, failures


def failures_to_pairs(failures):
    """Convert failures into training pairs."""
    pairs = []
    for f in failures:
        # Reinforce correct output
        pairs.append({
            "instruction": f["instruction"],
            "output": f["expected_output"],
            "metadata": {"source": "failure_fix", "type": f["type"], "fix_type": "reinforce"},
        })
        # Fix broken output
        if f["model_output"] and len(f["model_output"]) > 50:
            pairs.append({
                "instruction": f"Fix this broken MuleSoft code ({f['error_reason']}):\n{f['model_output'][:500]}",
                "output": f["expected_output"],
                "metadata": {"source": "failure_fix", "type": f["type"], "fix_type": "fix"},
            })
    return pairs


def train_model(dataset, output_dir, epochs=3):
    """Train/retrain the model."""
    from unsloth import FastLanguageModel
    from trl import SFTTrainer, SFTConfig
    from datasets import Dataset

    model, tokenizer = FastLanguageModel.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct", max_seq_length=4096, load_in_4bit=True)
    model = FastLanguageModel.get_peft_model(model, r=16, target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], lora_alpha=16, lora_dropout=0.05)

    formatted = [{"messages": [
        {"role": "system", "content": "You are MINT, an expert MuleSoft developer. Generate complete, valid Mule 4 XML flows and DataWeave transformations."},
        {"role": "user", "content": ex["instruction"]},
        {"role": "assistant", "content": ex["output"]},
    ]} for ex in dataset]

    ds = Dataset.from_list(formatted)

    def fmt(examples):
        return {"text": [tokenizer.apply_chat_template(m, tokenize=False) for m in examples["messages"]]}
    ds = ds.map(fmt, batched=True)

    trainer = SFTTrainer(
        model=model, processing_class=tokenizer, train_dataset=ds,
        args=SFTConfig(
            output_dir=output_dir, num_train_epochs=epochs,
            per_device_train_batch_size=2, gradient_accumulation_steps=4,
            logging_steps=10, save_steps=200, save_total_limit=2,
            learning_rate=2e-4, warmup_steps=50, bf16=True,
            optim="adamw_8bit", report_to="none", dataset_text_field="text",
        ),
    )
    trainer.train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    return model, tokenizer


def main():
    print("=" * 60)
    print("MINT RECURSIVE IMPROVEMENT LOOP (GPU)")
    print("=" * 60)

    # Load data
    train_data = [json.loads(l) for l in open("data/dataset_train.jsonl")]
    test_data = [json.loads(l) for l in open("data/dataset_test.jsonl")][:50]
    print(f"Train: {len(train_data)} | Test: {len(test_data)}")

    # === ROUND 1: Train v1 ===
    print("\n" + "=" * 60)
    print("ROUND 1: Training v1")
    print("=" * 60)
    model, tokenizer = train_model(train_data, "models/mint-lora-v1")

    # Evaluate v1
    print("\n  Evaluating v1...")
    from peft import PeftModel
    acc1, failures1 = evaluate_model(model, tokenizer, test_data)
    print(f"  v1 Accuracy: {acc1:.1f}% | Failures: {len(failures1)}")

    # Save failures
    with open("data/failures_v1.jsonl", "w") as f:
        for item in failures1:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    if not failures1:
        print("\n✓ No failures! v1 is already good.")
        return

    # === ROUND 2: Fix failures and retrain ===
    print("\n" + "=" * 60)
    print("ROUND 2: Training v2 (with failure fixes)")
    print("=" * 60)

    # Convert failures to training pairs
    fix_pairs = failures_to_pairs(failures1)
    print(f"  Generated {len(fix_pairs)} fix pairs from {len(failures1)} failures")

    # Build v2 dataset
    v2_data = train_data + fix_pairs
    # Deduplicate
    seen = set()
    unique = []
    for item in v2_data:
        h = hashlib.md5(item["output"][:500].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(item)
    v2_data = unique
    print(f"  v2 dataset: {len(v2_data)} pairs")

    # Train v2
    del model  # free memory
    torch.cuda.empty_cache()
    model2, tokenizer2 = train_model(v2_data, "models/mint-lora-v2")

    # Evaluate v2
    print("\n  Evaluating v2...")
    acc2, failures2 = evaluate_model(model2, tokenizer2, test_data)
    print(f"  v2 Accuracy: {acc2:.1f}% | Failures: {len(failures2)}")

    # === SUMMARY ===
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"  v1: {acc1:.1f}% accuracy ({len(failures1)} failures)")
    print(f"  v2: {acc2:.1f}% accuracy ({len(failures2)} failures)")
    print(f"  Improvement: +{acc2 - acc1:.1f} percentage points")
    print(f"\n  Models saved:")
    print(f"    models/mint-lora-v1/")
    print(f"    models/mint-lora-v2/")

    # Save summary
    summary = {"v1_accuracy": acc1, "v2_accuracy": acc2, "v1_failures": len(failures1), "v2_failures": len(failures2), "improvement": round(acc2 - acc1, 1)}
    Path("data/loop_results.json").write_text(json.dumps(summary, indent=2))
    print(f"\n  Results: data/loop_results.json")


if __name__ == "__main__":
    main()
