"""
MINT — Convert failures into new training examples.

Takes failures from collect_failures.py and creates:
1. "Fix this broken code" examples
2. "Complete this truncated code" examples
3. Better instruction/output pairs from the expected output

Output: data/training_fixes_v{N}.jsonl
"""

import json
import re
from pathlib import Path


def failure_to_training_pairs(failure: dict) -> list[dict]:
    """Convert a single failure into 1-3 training pairs."""
    pairs = []
    error = failure["error_reason"]
    model_output = failure["model_output"]
    expected = failure["expected_output"]
    instruction = failure["instruction"]
    sample_type = failure["type"]

    # Pair 1: Original instruction → correct output (reinforce correct behavior)
    pairs.append({
        "instruction": instruction,
        "output": expected,
        "metadata": {"source": "failure_fix", "type": sample_type, "fix_type": "reinforce"},
    })

    # Pair 2: "Fix this broken code" (teaches error correction)
    if "Truncated" in error:
        fix_instruction = f"Complete this truncated MuleSoft {sample_type}. The output was cut off:\n\n{model_output[:500]}"
        pairs.append({
            "instruction": fix_instruction,
            "output": expected,
            "metadata": {"source": "failure_fix", "type": sample_type, "fix_type": "complete_truncated"},
        })
    elif "XML parse error" in error or "missing closing" in error:
        fix_instruction = f"Fix this invalid Mule XML. Error: {error}\n\nBroken code:\n{model_output[:500]}"
        pairs.append({
            "instruction": fix_instruction,
            "output": expected,
            "metadata": {"source": "failure_fix", "type": sample_type, "fix_type": "fix_xml"},
        })
    elif "Missing" in error:
        fix_instruction = f"This MuleSoft flow is missing required components. {error}\n\nIncomplete code:\n{model_output[:500]}"
        pairs.append({
            "instruction": fix_instruction,
            "output": expected,
            "metadata": {"source": "failure_fix", "type": sample_type, "fix_type": "add_missing"},
        })

    # Pair 3: Explicit instruction about what went wrong
    if sample_type == "flow" and expected:
        # Extract what connectors should be there
        connectors = re.findall(r'<(\w+):(listener|request|query|create|update|publish|consume)', expected)
        if connectors:
            conn_list = ", ".join(set(f"{c[0]}:{c[1]}" for c in connectors))
            explicit_instruction = f"Create a complete Mule 4 flow that uses these connectors: {conn_list}. Include full XML with namespace declarations, flow definition, and all closing tags."
            pairs.append({
                "instruction": explicit_instruction,
                "output": expected,
                "metadata": {"source": "failure_fix", "type": sample_type, "fix_type": "explicit_connectors"},
            })

    return pairs


def convert_failures(version: int = 1):
    """Convert all failures from a version into training data."""
    failures_path = Path(f"data/failures_v{version}.jsonl")
    if not failures_path.exists():
        print(f"No failures file: {failures_path}")
        return

    failures = [json.loads(l) for l in open(failures_path)]
    print(f"Converting {len(failures)} failures into training pairs...")

    all_pairs = []
    for failure in failures:
        pairs = failure_to_training_pairs(failure)
        all_pairs.extend(pairs)

    # Save
    output_path = Path(f"data/training_fixes_v{version}.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for pair in all_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    print(f"  Generated {len(all_pairs)} new training pairs")
    print(f"  Saved: {output_path}")
    print(f"\n  Breakdown:")
    fix_types = {}
    for p in all_pairs:
        ft = p["metadata"].get("fix_type", "unknown")
        fix_types[ft] = fix_types.get(ft, 0) + 1
    for ft, count in sorted(fix_types.items()):
        print(f"    {ft}: {count}")

    return all_pairs


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=1)
    args = parser.parse_args()
    convert_failures(args.version)
