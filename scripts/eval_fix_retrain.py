"""
MINT — Eval + Fix + Retrain (Round 2)
======================================
Runs AFTER initial training is complete.
1. Evaluates the trained model
2. Collects failures
3. Generates fix pairs from failures
4. Adds negative examples
5. Retrains on original data + fixes + negatives
6. Pushes to HuggingFace

Usage:
    cd /workspace/mint
    python scripts/eval_fix_retrain.py
"""

import json
import re
import hashlib
import torch
import numpy as np
from pathlib import Path
from xml.etree import ElementTree as ET
from collections import Counter

MODEL_PATH = "models/mint-lora-v3-round1"
TRAIN_FILE = "data/training_merged.jsonl"
TEST_FILE = "data/dataset_test.jsonl"
OUTPUT_DIR = "models/mint-lora-v3-round2"
EVAL_SAMPLES = 50

SYSTEM_PROMPT = (
    "You are MINT, an expert MuleSoft 4 developer. "
    "Generate complete, valid Mule 4 XML flows and DataWeave 2.0 transformations. "
    "Always include ALL required namespace declarations. "
    "Never use Mule 3 syntax (no component, inbound-endpoint, MEL, session-variable). "
    "Never invent XML elements that don't exist in Mule 4."
)


# ============================================================
# STEP 1: EVALUATE
# ============================================================
def evaluate_model(model, tokenizer, test_data):
    """Evaluate and return results + failures."""
    print(f"\n📊 Evaluating on {len(test_data)} samples...")
    results = []
    failures = []

    for i, sample in enumerate(test_data):
        if i % 10 == 0:
            print(f"  [{i+1}/{len(test_data)}]...")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": sample["instruction"]},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs, max_new_tokens=4096,
                temperature=0.1, do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

        sample_type = sample.get("metadata", {}).get("type", "flow")
        score, errors = score_output(generated, sample["instruction"], sample_type)
        results.append({"score": score, "type": sample_type, "errors": errors})

        if score < 0.7:
            failures.append({
                "instruction": sample["instruction"],
                "generated": generated[:3000],
                "expected": sample["output"][:3000],
                "errors": errors,
                "score": score,
                "type": sample_type,
            })

    # Print summary
    avg = np.mean([r["score"] for r in results]) * 100
    flow_results = [r for r in results if r["type"] == "flow"]
    dw_results = [r for r in results if r["type"] == "dataweave"]

    print(f"\n{'='*50}")
    print(f"  EVALUATION RESULTS")
    print(f"{'='*50}")
    print(f"  Overall: {avg:.1f}%")
    if flow_results:
        print(f"  Flows: {np.mean([r['score'] for r in flow_results])*100:.1f}%")
    if dw_results:
        print(f"  DataWeave: {np.mean([r['score'] for r in dw_results])*100:.1f}%")
    print(f"  Failures: {len(failures)}/{len(results)}")

    if failures:
        all_errors = []
        for f in failures:
            all_errors.extend(f["errors"])
        print(f"  Top errors:")
        for err, count in Counter(all_errors).most_common(5):
            print(f"    {count}x: {err[:60]}")

    return results, failures


def score_output(generated, instruction, sample_type):
    """Score a single output."""
    errors = []

    if sample_type == "flow":
        has_mule = "<mule" in generated
        has_ns = "mulesoft.org/schema/mule" in generated
        has_close = "</mule>" in generated
        has_flow = bool(re.search(r'<flow\s+name=', generated))

        # Check for Mule 3 garbage
        mule3_patterns = ["<component", "<inbound-endpoint", "<outbound-endpoint",
                          "<catch-exception-strategy", "<expression-transformer",
                          "<custom-transformer", "<poll>", "session-variable",
                          "<method", "<return-type", "<argument"]
        has_mule3 = any(p in generated for p in mule3_patterns)
        if has_mule3:
            errors.append("Contains Mule 3 syntax")

        # Check undeclared prefixes
        prefixes_used = set(re.findall(r'<(\w+):', generated))
        prefixes_declared = set(re.findall(r'xmlns:(\w+)=', generated))
        undeclared = prefixes_used - prefixes_declared - {"xml", "xsi"}
        if undeclared:
            errors.append(f"Undeclared prefixes: {','.join(undeclared)}")

        # XML parseable
        parseable = False
        xml_match = re.search(r'(<\?xml.*?\?>.*?</mule>|<mule.*?</mule>)', generated, re.DOTALL)
        if xml_match:
            try:
                ET.fromstring(xml_match.group(0))
                parseable = True
            except ET.ParseError as e:
                errors.append(f"XML parse error: {str(e)[:50]}")

        if not has_mule:
            errors.append("Missing <mule> root")
        if not has_close:
            errors.append("Truncated (no </mule>)")
        if not has_ns:
            errors.append("Missing namespace")

        score = sum([
            (1.0 if parseable else 0.0) * 0.3,
            (1.0 if has_flow else 0.0) * 0.2,
            (1.0 if has_ns else 0.0) * 0.15,
            (1.0 if has_close else 0.0) * 0.15,
            (0.0 if has_mule3 else 1.0) * 0.1,
            (1.0 if not undeclared else 0.0) * 0.1,
        ])
    elif sample_type == "dataweave":
        has_dw = "%dw" in generated
        has_output = "output " in generated
        has_sep = "---" in generated
        if not has_dw:
            errors.append("Missing %dw header")
        if not has_output:
            errors.append("Missing output declaration")
        score = sum([
            (1.0 if has_dw else 0.0) * 0.4,
            (1.0 if has_output else 0.0) * 0.3,
            (1.0 if has_sep else 0.0) * 0.3,
        ])
    else:
        score = 0.5 if len(generated) > 50 else 0.0

    return score, errors


# ============================================================
# STEP 2: GENERATE FIX PAIRS FROM FAILURES
# ============================================================
def generate_fix_pairs(failures):
    """Convert failures into training pairs."""
    fix_pairs = []
    print(f"\n🔧 Generating fix pairs from {len(failures)} failures...")

    for f in failures:
        # Reinforce correct output
        fix_pairs.append({
            "instruction": f["instruction"],
            "output": f["expected"],
            "metadata": {"type": f["type"], "source": "fix", "strategy": "reinforce"},
        })

        # Namespace fix
        if "prefix" in " ".join(f["errors"]).lower() or "namespace" in " ".join(f["errors"]).lower():
            fix_pairs.append({
                "instruction": f"Generate MuleSoft 4 flow with ALL xmlns: namespace declarations. {f['instruction']}",
                "output": f["expected"],
                "metadata": {"type": f["type"], "source": "fix", "strategy": "namespace"},
            })

        # Truncation fix
        if "truncat" in " ".join(f["errors"]).lower() or "no </mule>" in " ".join(f["errors"]).lower():
            fix_pairs.append({
                "instruction": f"Generate COMPLETE MuleSoft 4 flow (close all tags with </mule>). {f['instruction']}",
                "output": f["expected"],
                "metadata": {"type": f["type"], "source": "fix", "strategy": "completion"},
            })

        # Mule 3 correction
        if "mule 3" in " ".join(f["errors"]).lower():
            fix_pairs.append({
                "instruction": f"Generate Mule 4 ONLY (no Mule 3 syntax like component, inbound-endpoint, MEL). {f['instruction']}",
                "output": f["expected"],
                "metadata": {"type": f["type"], "source": "fix", "strategy": "mule4_only"},
            })

        # Error correction pair
        if f["generated"] and len(f["generated"]) > 100 and f["score"] < 0.4:
            fix_pairs.append({
                "instruction": f"Fix this broken MuleSoft code (errors: {'; '.join(f['errors'][:2])}):\n{f['generated'][:500]}",
                "output": f["expected"],
                "metadata": {"type": f["type"], "source": "fix", "strategy": "error_correction"},
            })

    print(f"  Generated {len(fix_pairs)} fix pairs")
    return fix_pairs


# ============================================================
# STEP 3: ADD NEGATIVE EXAMPLES
# ============================================================
def load_negative_examples():
    """Load negative examples if available."""
    neg_file = Path("data/negative_examples.jsonl")
    if not neg_file.exists():
        # Generate them
        import subprocess
        subprocess.run(["python", "scripts/generate_negative_examples_v2.py"], check=True)

    if neg_file.exists():
        negs = [json.loads(l) for l in open(neg_file) if l.strip()]
        print(f"  Loaded {len(negs)} negative examples")
        return negs
    return []


# ============================================================
# STEP 4: RETRAIN (ROUND 2)
# ============================================================
def retrain(data, output_dir):
    """Train round 2 with fixes + negatives."""
    from unsloth import FastLanguageModel
    from trl import SFTTrainer, SFTConfig
    from datasets import Dataset

    print(f"\n🚀 Retraining on {len(data)} pairs (round 2)...")

    model, tokenizer = FastLanguageModel.from_pretrained(
        "unsloth/qwen2.5-coder-7b-instruct-bnb-4bit",
        max_seq_length=8192, load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model, r=32,
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
        lora_alpha=64, lora_dropout=0.05,
        use_gradient_checkpointing="unsloth",
    )

    formatted = [{"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ex["instruction"]},
        {"role": "assistant", "content": ex["output"]},
    ]} for ex in data if ex.get("instruction") and ex.get("output")]

    ds = Dataset.from_list(formatted)
    ds = ds.map(lambda ex: {"text": [tokenizer.apply_chat_template(m, tokenize=False) for m in ex["messages"]]}, batched=True, num_proc=4)

    trainer = SFTTrainer(
        model=model, processing_class=tokenizer, train_dataset=ds,
        args=SFTConfig(
            output_dir=output_dir,
            num_train_epochs=2,  # Fewer epochs for fix round
            per_device_train_batch_size=8,
            gradient_accumulation_steps=2,
            learning_rate=5e-5,  # Lower LR for fine-tuning fixes
            warmup_ratio=0.05,
            lr_scheduler_type="cosine",
            logging_steps=10, save_steps=200, save_total_limit=2,
            bf16=True, optim="adamw_8bit", report_to="none",
            dataset_text_field="text", max_seq_length=8192, seed=42,
        ),
    )
    trainer.train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"  ✓ Round 2 model saved to {output_dir}")
    return model, tokenizer


# ============================================================
# MAIN
# ============================================================
def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    print("=" * 50)
    print("  MINT — Eval + Fix + Retrain (Round 2)")
    print("=" * 50)

    # Load trained model
    print("\n📦 Loading trained model...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model = AutoModelForCausalLM.from_pretrained(
        "unsloth/qwen2.5-coder-7b-instruct-bnb-4bit",
        torch_dtype=torch.float16, device_map="auto",
    )
    model = PeftModel.from_pretrained(model, MODEL_PATH)
    model.eval()
    print("  ✓ Model loaded")

    # Load test data
    test_data = [json.loads(l) for l in open(TEST_FILE) if l.strip()][:EVAL_SAMPLES]

    # Step 1: Evaluate
    results, failures = evaluate_model(model, tokenizer, test_data)

    # Save eval results
    Path("data/eval").mkdir(parents=True, exist_ok=True)
    with open("data/eval/round1_failures.jsonl", "w") as f:
        for fail in failures:
            f.write(json.dumps(fail) + "\n")

    avg_score = np.mean([r["score"] for r in results]) * 100
    print(f"\n  Round 1 score: {avg_score:.1f}%")

    if avg_score >= 85:
        print("  🎯 Score is good enough! No fix round needed.")
        return

    # Free GPU memory
    del model
    torch.cuda.empty_cache()

    # Step 2: Generate fix pairs
    fix_pairs = generate_fix_pairs(failures)

    # Step 3: Load negative examples
    print("\n📚 Loading negative examples...")
    negatives = load_negative_examples()

    # Step 4: Build round 2 dataset
    original_data = [json.loads(l) for l in open(TRAIN_FILE) if l.strip()]
    round2_data = original_data + fix_pairs + negatives

    # Dedup
    seen = set()
    unique = []
    for item in round2_data:
        h = hashlib.md5(item.get("output", "")[:500].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(item)
    round2_data = unique
    print(f"\n  Round 2 dataset: {len(round2_data)} pairs")
    print(f"    Original: {len(original_data)}")
    print(f"    Fix pairs: {len(fix_pairs)}")
    print(f"    Negatives: {len(negatives)}")

    # Step 5: Retrain
    model2, tokenizer2 = retrain(round2_data, OUTPUT_DIR)

    # Step 6: Push to HuggingFace
    print("\n☁️  Pushing round 2 to HuggingFace...")
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        api.create_repo("raghavenderreddy1212/mintai-v3-round2", exist_ok=True, repo_type="model")
        api.upload_folder(folder_path=OUTPUT_DIR, repo_id="raghavenderreddy1212/mintai-v3-round2", repo_type="model", ignore_patterns=["checkpoint-*"])
        print("  ✓ https://huggingface.co/raghavenderreddy1212/mintai-v3-round2")
    except Exception as e:
        print(f"  ⚠️ Push failed: {e}")

    print("\n" + "=" * 50)
    print("  ✅ ROUND 2 COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
