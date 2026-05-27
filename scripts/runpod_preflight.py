"""
MINT RunPod Preflight Check
=============================
Run this FIRST on your RunPod instance to verify:
1. GPU is available
2. HuggingFace auth works
3. Required packages installed
4. Can push to your HF repo
5. Can load base model

Usage:
    # Set your HF token (use environment variable, NOT hardcoded)
    export HF_TOKEN="hf_your_new_token_here"

    # Or login interactively:
    huggingface-cli login

    # Then run:
    python scripts/runpod_preflight.py
"""

import os
import sys


def check_gpu():
    """Check GPU availability."""
    print("\n1️⃣  GPU Check")
    print("-" * 40)
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_mem
            gpu_mem_gb = gpu_mem / (1024**3)
            print(f"  ✓ GPU: {gpu_name}")
            print(f"  ✓ VRAM: {gpu_mem_gb:.1f} GB")
            if gpu_mem_gb < 16:
                print(f"  ⚠️  Low VRAM. 4-bit training needs ~18GB. Consider larger GPU.")
            return True
        else:
            print("  ✗ No GPU detected! Training will be extremely slow.")
            return False
    except ImportError:
        print("  ✗ PyTorch not installed")
        return False


def check_hf_auth():
    """Check HuggingFace authentication."""
    print("\n2️⃣  HuggingFace Auth")
    print("-" * 40)

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    if not token:
        # Check if logged in via huggingface-cli
        try:
            from huggingface_hub import HfApi
            api = HfApi()
            info = api.whoami()
            print(f"  ✓ Logged in as: {info['name']}")
            return True
        except Exception:
            print("  ✗ Not authenticated!")
            print("  Fix: export HF_TOKEN='hf_your_token'")
            print("  Or:  huggingface-cli login")
            return False
    else:
        try:
            from huggingface_hub import HfApi
            api = HfApi(token=token)
            info = api.whoami()
            print(f"  ✓ Authenticated as: {info['name']}")
            print(f"  ✓ Token: {token[:8]}...{token[-4:]}")
            return True
        except Exception as e:
            print(f"  ✗ Token invalid: {e}")
            print("  Fix: Get new token at https://huggingface.co/settings/tokens")
            return False


def check_hf_push():
    """Check if we can push to the target repo."""
    print("\n3️⃣  HuggingFace Push Access")
    print("-" * 40)
    try:
        from huggingface_hub import HfApi
        api = HfApi()

        # Try to create/access the repo
        repo_id = "raghavenderreddy1212/mintai-v3-test"
        try:
            api.create_repo(repo_id, exist_ok=True, private=False)
            print(f"  ✓ Can create/access repos under raghavenderreddy1212/")
            # Clean up test repo
            try:
                api.delete_repo(repo_id)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"  ✗ Cannot push: {e}")
            print("  Fix: Ensure token has 'write' permission")
            return False
    except ImportError:
        print("  ✗ huggingface_hub not installed")
        return False


def check_packages():
    """Check required packages."""
    print("\n4️⃣  Required Packages")
    print("-" * 40)

    packages = {
        "unsloth": "unsloth",
        "trl": "trl",
        "datasets": "datasets",
        "peft": "peft",
        "transformers": "transformers",
        "accelerate": "accelerate",
        "bitsandbytes": "bitsandbytes",
        "huggingface_hub": "huggingface_hub",
        "chromadb": "chromadb",
        "sentence_transformers": "sentence-transformers",
        "numpy": "numpy",
    }

    all_ok = True
    for import_name, pip_name in packages.items():
        try:
            __import__(import_name)
            print(f"  ✓ {pip_name}")
        except ImportError:
            print(f"  ✗ {pip_name} — pip install {pip_name}")
            all_ok = False

    return all_ok


def check_model_load():
    """Check if base model can be loaded."""
    print("\n5️⃣  Base Model Load")
    print("-" * 40)
    try:
        from unsloth import FastLanguageModel
        print("  Loading unsloth/qwen2.5-coder-7b-instruct-bnb-4bit...")
        model, tokenizer = FastLanguageModel.from_pretrained(
            "unsloth/qwen2.5-coder-7b-instruct-bnb-4bit",
            max_seq_length=8192,
            load_in_4bit=True,
        )
        print(f"  ✓ Model loaded successfully")
        print(f"  ✓ Vocab size: {tokenizer.vocab_size}")
        del model
        import torch
        torch.cuda.empty_cache()
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def check_data():
    """Check if training data exists."""
    print("\n6️⃣  Training Data")
    print("-" * 40)
    from pathlib import Path

    files = {
        "data/training_merged.jsonl": "Merged training data (10K+)",
        "data/dataset_train.jsonl": "Original training data (1.7K)",
        "data/dataset_test.jsonl": "Test data",
    }

    found_train = False
    for path, desc in files.items():
        p = Path(path)
        if p.exists():
            lines = sum(1 for _ in open(p))
            print(f"  ✓ {path} ({lines} pairs) — {desc}")
            if "train" in path:
                found_train = True
        else:
            print(f"  - {path} not found — {desc}")

    if not found_train:
        print("  ⚠️  No training data! Run scrapers first or upload data.")
    return found_train


def main():
    print("=" * 50)
    print("  MINT — RunPod Preflight Check")
    print("=" * 50)
    print("\n  ⚡ Step 0: HuggingFace Authentication")
    print("  " + "-" * 40)
    print("  Before anything else, authenticate:")
    print("    export HF_TOKEN='hf_your_write_token'")
    print("    # Get token: https://huggingface.co/settings/tokens")
    print("    # Needs WRITE access for pushing models")
    print()

    results = {}
    results["gpu"] = check_gpu()
    results["hf_auth"] = check_hf_auth()
    results["hf_push"] = check_hf_push()
    results["packages"] = check_packages()
    results["data"] = check_data()

    # Only try model load if GPU + packages are good
    if results["gpu"] and results["packages"]:
        results["model_load"] = check_model_load()
    else:
        results["model_load"] = False
        print("\n5️⃣  Base Model Load")
        print("-" * 40)
        print("  ⏭️  Skipped (fix GPU/packages first)")

    # Summary
    print("\n" + "=" * 50)
    print("  SUMMARY")
    print("=" * 50)
    all_pass = all(results.values())

    for check, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

    if all_pass:
        print("\n  🎉 All checks passed! Ready to train.")
        print("\n  Next steps:")
        print("    python scripts/train_eval_fix_pipeline.py")
    else:
        print("\n  ⚠️  Fix the issues above before training.")
        if not results["hf_auth"]:
            print("\n  To authenticate with HuggingFace:")
            print("    export HF_TOKEN='hf_your_token_here'")
            print("    # OR")
            print("    pip install huggingface_hub")
            print("    huggingface-cli login")
        if not results["packages"]:
            print("\n  To install all packages:")
            print("    pip install unsloth trl datasets peft transformers")
            print("    pip install accelerate bitsandbytes huggingface_hub")
            print("    pip install chromadb sentence-transformers")


if __name__ == "__main__":
    main()
