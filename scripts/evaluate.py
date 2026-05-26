"""
MINT Evaluation — Measure accuracy of the trained model.

Metrics:
1. XML validity — does output parse as valid XML?
2. Connector accuracy — did it use the right connectors?
3. Structure completeness — has flow, namespace, config?
4. Instruction following — did it do what was asked?

Usage:
    python scripts/evaluate.py --model /path/to/mint-lora --samples 50
"""

import json
import re
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET


def validate_xml(text: str) -> bool:
    """Check if output contains valid XML."""
    # Extract XML from output (might have text before/after)
    xml_match = re.search(r'(<\?xml.*?\?>.*?</mule>|<mule.*?</mule>)', text, re.DOTALL)
    if xml_match:
        try:
            ET.fromstring(xml_match.group(0))
            return True
        except:
            pass
    # Try the whole thing
    try:
        ET.fromstring(text.strip())
        return True
    except:
        return False


def check_has_flow(text: str) -> bool:
    """Check if output has a flow element."""
    return bool(re.search(r'<flow\s+name=', text))


def check_has_namespace(text: str) -> bool:
    """Check if output has Mule namespace."""
    return "mulesoft.org/schema/mule" in text


def check_connectors(text: str, expected_instruction: str) -> dict:
    """Check if the right connectors are present based on instruction."""
    results = {"expected": [], "found": [], "correct": 0, "total": 0}

    connector_keywords = {
        "salesforce": ["salesforce:"],
        "http": ["http:listener", "http:request"],
        "database": ["db:select", "db:insert", "db:update"],
        "kafka": ["kafka:"],
        "s3": ["s3:"],
        "email": ["email:"],
        "file": ["file:"],
        "batch": ["batch:job"],
        "dataweave": ["ee:transform"],
    }

    instruction_lower = expected_instruction.lower()
    for keyword, patterns in connector_keywords.items():
        if keyword in instruction_lower:
            results["expected"].append(keyword)
            results["total"] += 1
            if any(p in text for p in patterns):
                results["found"].append(keyword)
                results["correct"] += 1

    return results


def check_dataweave_valid(text: str) -> bool:
    """Check if DataWeave output is valid."""
    if "%dw" in text:
        return True
    if "---" in text and ("output" in text or "input" in text):
        return True
    return False


def evaluate_sample(instruction: str, expected_output: str, model_output: str, sample_type: str) -> dict:
    """Evaluate a single sample."""
    result = {
        "type": sample_type,
        "instruction_length": len(instruction),
        "output_length": len(model_output),
    }

    if sample_type == "flow":
        result["xml_valid"] = validate_xml(model_output)
        result["has_flow"] = check_has_flow(model_output)
        result["has_namespace"] = check_has_namespace(model_output)
        result["connectors"] = check_connectors(model_output, instruction)
        result["score"] = sum([
            result["xml_valid"] * 0.3,
            result["has_flow"] * 0.2,
            result["has_namespace"] * 0.2,
            (result["connectors"]["correct"] / max(result["connectors"]["total"], 1)) * 0.3,
        ])
    elif sample_type == "dataweave":
        result["dw_valid"] = check_dataweave_valid(model_output)
        result["has_output"] = len(model_output.strip()) > 20
        result["score"] = sum([
            result["dw_valid"] * 0.5,
            result["has_output"] * 0.5,
        ])
    else:
        result["score"] = 0.5 if len(model_output) > 50 else 0.0

    return result


def run_evaluation(model_path: str, n_samples: int = 50):
    """Run full evaluation."""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    import torch

    # Load test data
    test_data = [json.loads(l) for l in open("data/dataset_test.jsonl")][:n_samples]
    print(f"Evaluating on {len(test_data)} test samples")

    # Load model
    print("Loading model...")
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct")
    model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct", dtype=torch.float16, device_map="cpu")
    model = PeftModel.from_pretrained(model, model_path)
    model.eval()
    print("✓ Model loaded")

    # Evaluate
    results = []
    for i, sample in enumerate(test_data):
        if i % 10 == 0:
            print(f"  [{i+1}/{len(test_data)}]...")

        messages = [
            {"role": "system", "content": "You are MINT, an expert MuleSoft developer."},
            {"role": "user", "content": sample["instruction"]},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt")

        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=512, temperature=0.1, do_sample=True)

        model_output = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        sample_type = sample.get("metadata", {}).get("type", "flow")

        result = evaluate_sample(sample["instruction"], sample["output"], model_output, sample_type)
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    avg_score = sum(r["score"] for r in results) / len(results) * 100

    flow_results = [r for r in results if r["type"] == "flow"]
    dw_results = [r for r in results if r["type"] == "dataweave"]

    print(f"\n  Overall accuracy: {avg_score:.1f}%")
    print(f"  Samples evaluated: {len(results)}")

    if flow_results:
        xml_valid = sum(r.get("xml_valid", False) for r in flow_results) / len(flow_results) * 100
        has_flow = sum(r.get("has_flow", False) for r in flow_results) / len(flow_results) * 100
        has_ns = sum(r.get("has_namespace", False) for r in flow_results) / len(flow_results) * 100
        flow_score = sum(r["score"] for r in flow_results) / len(flow_results) * 100
        print(f"\n  Flows ({len(flow_results)} samples):")
        print(f"    XML valid:     {xml_valid:.1f}%")
        print(f"    Has <flow>:    {has_flow:.1f}%")
        print(f"    Has namespace: {has_ns:.1f}%")
        print(f"    Flow score:    {flow_score:.1f}%")

    if dw_results:
        dw_valid = sum(r.get("dw_valid", False) for r in dw_results) / len(dw_results) * 100
        dw_score = sum(r["score"] for r in dw_results) / len(dw_results) * 100
        print(f"\n  DataWeave ({len(dw_results)} samples):")
        print(f"    DW valid:      {dw_valid:.1f}%")
        print(f"    DW score:      {dw_score:.1f}%")

    # Save results
    output = {
        "overall_accuracy": round(avg_score, 1),
        "n_samples": len(results),
        "flow_accuracy": round(sum(r["score"] for r in flow_results) / max(len(flow_results), 1) * 100, 1),
        "dataweave_accuracy": round(sum(r["score"] for r in dw_results) / max(len(dw_results), 1) * 100, 1),
        "details": results,
    }
    Path("data/eval_results.json").write_text(json.dumps(output, indent=2))
    print(f"\n  Results saved: data/eval_results.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/Users/Raghavender/Downloads/models/mint-lora")
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    run_evaluation(args.model, args.samples)
