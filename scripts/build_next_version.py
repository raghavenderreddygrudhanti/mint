"""
MINT — Build next training version by merging original + failure fixes.

Combines:
  data/dataset_train.jsonl (original)
  data/training_fixes_v{N}.jsonl (failure-derived)
  → data/dataset_train_v{N+1}.jsonl

Usage:
    python scripts/build_next_version.py --version 2
"""

import json
import hashlib
from pathlib import Path


def build_next_version(version: int = 2):
    """Build the next training dataset version."""
    # Load original training data
    original = [json.loads(l) for l in open("data/dataset_train.jsonl")]
    print(f"Original training data: {len(original)} pairs")

    # Load all fix data up to this version
    all_fixes = []
    for v in range(1, version):
        fixes_path = Path(f"data/training_fixes_v{v}.jsonl")
        if fixes_path.exists():
            fixes = [json.loads(l) for l in open(fixes_path)]
            all_fixes.extend(fixes)
            print(f"  + fixes v{v}: {len(fixes)} pairs")

    print(f"Total fixes: {len(all_fixes)}")

    # Combine
    combined = original + all_fixes

    # Deduplicate by output hash
    seen = set()
    unique = []
    for item in combined:
        h = hashlib.md5(item["output"][:500].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(item)

    print(f"Combined (after dedup): {len(unique)} pairs")

    # Save
    output_path = Path(f"data/dataset_train_v{version}.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for item in unique:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Saved: {output_path} ({output_path.stat().st_size / 1e6:.1f} MB)")

    # Also update the main training file for the train script
    main_path = Path("data/dataset_train.jsonl")
    with open(main_path, "w", encoding="utf-8") as f:
        for item in unique:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Updated: {main_path}")

    return unique


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=2)
    args = parser.parse_args()
    build_next_version(args.version)
