"""
MINT — Collect failures from evaluation for retraining.

Runs the model on test data, identifies failures, and saves them
with error reasons for the next training round.

Output: data/failures_v{N}.jsonl
"""

import json
import re
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET


def validate_xml(text: str) -> tuple[bool, str]:
    """Check XML validity, return (valid, error_reason)."""
    xml_match = re.search(r'(<\?xml.*?\?>.*?</mule>|<mule.*?</mule>)', text, re.DOTALL)
    if xml_match:
        try:
            ET.fromstring(xml_match.group(0))
            return True, ""
        except ET.ParseError as e:
            return False, f"XML parse error: {str(e)[:100]}"

    # Check for common issues
    if "<mule" in text and "</mule>" not in text:
        return False, "Truncated: missing closing </mule> tag"
    if "<flow" in text and "</flow>" not in text:
        return False, "Truncated: missing closing </flow> tag"
    if "<mule" not in text and "<flow" not in text:
        return False, "Not MuleSoft XML: no <mule> or <flow> element"

    try:
        ET.fromstring(text.strip())
        return True, ""
    except ET.ParseError as e:
        return False, f"XML parse error: {str(e)[:100]}"


def validate_dataweave(text: str) -> tuple[bool, str]:
    """Check DataWeave validity."""
    if not text.strip():
        return False, "Empty output"
    if len(text.strip()) < 20:
        return False, "Output too short (< 20 chars)"
    if "%dw" in text or "---" in text:
        return True, ""
    if text.strip().startswith("{") or text.strip().startswith("["):
        return True, ""
    return False, "No DataWeave syntax found (missing %dw or ---)"


def check_instruction_following(instruction: str, output: str) -> tuple[bool, str]:
    """Check if output follows the instruction."""
    instruction_lower = instruction.lower()
    errors = []

    # Check connectors mentioned in instruction are in output
    connector_checks = {
        "salesforce": "salesforce:",
        "http listener": "http:listener",
        "http request": "http:request",
        "database": "db:",
        "kafka": "kafka:",
        "s3": "s3:",
        "email": "email:",
        "batch": "batch:job",
        "dataweave": "ee:transform",
    }

    for keyword, expected_pattern in connector_checks.items():
        if keyword in instruction_lower and expected_pattern not in output:
            errors.append(f"Missing {keyword} connector (expected {expected_pattern})")

    if errors:
        return False, "; ".join(errors[:3])
    return True, ""


def collect_failures(model_path: str, n_samples: int = 50, version: int = 1):
    """Run model on test data and collect failures."""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    import torch

    # Load test data
    test_data = [json.loads(l) for l in open("data/dataset_test.jsonl")][:n_samples]
    print(f"Testing {len(test_data)} samples...")

    # Load model
    print("Loading model...")
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct")
    model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct", dtype=torch.float16, device_map="cpu")
    model = PeftModel.from_pretrained(model, model_path)
    model.eval()
    print("✓ Model loaded")

    failures = []
    successes = 0

    for i, sample in enumerate(test_data):
        if i % 5 == 0:
            print(f"  [{i+1}/{len(test_data)}]...")

        messages = [
            {"role": "system", "content": "You are MINT, an expert MuleSoft developer. Generate complete, valid Mule 4 XML flows and DataWeave transformations."},
            {"role": "user", "content": sample["instruction"]},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt")

        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=2048, temperature=0.1, do_sample=True)

        model_output = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        sample_type = sample.get("metadata", {}).get("type", "flow")

        # Validate
        is_valid = True
        error_reason = ""

        if sample_type == "flow":
            xml_valid, xml_error = validate_xml(model_output)
            if not xml_valid:
                is_valid = False
                error_reason = xml_error
            else:
                instr_valid, instr_error = check_instruction_following(sample["instruction"], model_output)
                if not instr_valid:
                    is_valid = False
                    error_reason = instr_error
        elif sample_type == "dataweave":
            dw_valid, dw_error = validate_dataweave(model_output)
            if not dw_valid:
                is_valid = False
                error_reason = dw_error

        if is_valid:
            successes += 1
        else:
            failures.append({
                "instruction": sample["instruction"],
                "model_output": model_output[:3000],
                "expected_output": sample["output"][:3000],
                "error_reason": error_reason,
                "type": sample_type,
            })

    # Save failures
    output_path = Path(f"data/failures_v{version}.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for item in failures:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    accuracy = successes / len(test_data) * 100
    print(f"\n{'=' * 60}")
    print(f"RESULTS (v{version})")
    print(f"{'=' * 60}")
    print(f"  Accuracy: {accuracy:.1f}% ({successes}/{len(test_data)})")
    print(f"  Failures: {len(failures)}")
    print(f"  Saved: {output_path}")

    # Breakdown
    flow_failures = [f for f in failures if f["type"] == "flow"]
    dw_failures = [f for f in failures if f["type"] == "dataweave"]
    print(f"\n  Flow failures: {len(flow_failures)}")
    print(f"  DataWeave failures: {len(dw_failures)}")

    if failures:
        print(f"\n  Top error reasons:")
        reasons = {}
        for f in failures:
            r = f["error_reason"][:50]
            reasons[r] = reasons.get(r, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1])[:5]:
            print(f"    {count}× {reason}")

    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/Users/Raghavender/Downloads/models/mint-lora")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--version", type=int, default=1)
    args = parser.parse_args()
    collect_failures(args.model, args.samples, args.version)
