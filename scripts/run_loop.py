"""
MINT — Recursive improvement loop orchestrator.

Runs the full cycle:
  1. Evaluate current model → collect failures
  2. Convert failures → new training pairs
  3. Build next dataset version
  4. Print instructions for retraining

Usage:
    # Run locally (evaluation only, slow on CPU)
    python scripts/run_loop.py --model /path/to/mint-lora --version 1 --samples 20

    # After running, retrain on RunPod with the new dataset
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_loop(model_path: str, version: int, samples: int):
    print("=" * 60)
    print(f"MINT RECURSIVE IMPROVEMENT — Round {version}")
    print("=" * 60)

    # Step 1: Collect failures
    print(f"\n[1/3] Collecting failures (v{version})...")
    from scripts.collect_failures import collect_failures
    failures = collect_failures(model_path, n_samples=samples, version=version)

    if not failures:
        print("\n✓ No failures! Model is performing well.")
        print("  Consider testing with more samples or harder tasks.")
        return

    # Step 2: Convert failures to training data
    print(f"\n[2/3] Converting {len(failures)} failures to training pairs...")
    from scripts.failures_to_training import convert_failures
    new_pairs = convert_failures(version=version)

    # Step 3: Build next dataset
    print(f"\n[3/3] Building dataset v{version + 1}...")
    from scripts.build_next_version import build_next_version
    dataset = build_next_version(version=version + 1)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"ROUND {version} COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Failures found: {len(failures)}")
    print(f"  New training pairs: {len(new_pairs) if new_pairs else 0}")
    print(f"  Next dataset size: {len(dataset)}")
    print(f"\n  NEXT STEP: Retrain on RunPod with updated dataset")
    print(f"  Command:")
    print(f"    cd /workspace && rm -rf mint && git clone <repo> && cd mint")
    print(f"    pip install unsloth datasets trl -q")
    print(f"    python scripts/train_cuda.py")
    print(f"\n  The training script will automatically use the updated dataset.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/Users/Raghavender/Downloads/models/mint-lora")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    run_loop(args.model, args.version, args.samples)
