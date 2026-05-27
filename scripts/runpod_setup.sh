#!/bin/bash
# ============================================================
# MINT — RunPod One-Time Setup
# ============================================================
# Run this ONCE when you first connect to your RunPod instance.
#
# Usage:
#   chmod +x scripts/runpod_setup.sh
#   ./scripts/runpod_setup.sh
# ============================================================

set -e

echo "=============================================="
echo "  MINT — RunPod Setup"
echo "=============================================="

# 1. Clone the repo
echo ""
echo "📦 Step 1: Clone repo..."
if [ ! -d "/workspace/mint" ]; then
    git clone https://github.com/raghavenderreddygrudhanti/mint.git /workspace/mint
    cd /workspace/mint
    git checkout v3-pipeline
else
    cd /workspace/mint
    git pull
    git checkout v3-pipeline
fi

echo "✓ Repo ready at /workspace/mint"

# 2. Install packages
echo ""
echo "📦 Step 2: Installing packages..."
pip install -q unsloth trl datasets peft transformers accelerate bitsandbytes
pip install -q huggingface_hub chromadb sentence-transformers
pip install -q requests beautifulsoup4 lxml tqdm tenacity PyGithub

echo "✓ Packages installed"

# 3. HuggingFace login
echo ""
echo "🔑 Step 3: HuggingFace Authentication"
echo "--------------------------------------"
if [ -z "$HF_TOKEN" ]; then
    echo "  No HF_TOKEN found in environment."
    echo ""
    echo "  Option A: Set it now:"
    echo "    export HF_TOKEN='hf_your_token_here'"
    echo ""
    echo "  Option B: Login interactively:"
    echo "    huggingface-cli login"
    echo ""
    echo "  Get a token at: https://huggingface.co/settings/tokens"
    echo "  (Needs WRITE access)"
    echo ""
    read -p "  Paste your HF token here (or press Enter to skip): " token
    if [ -n "$token" ]; then
        export HF_TOKEN="$token"
        echo "export HF_TOKEN='$token'" >> ~/.bashrc
        huggingface-cli login --token "$token"
        echo "  ✓ Authenticated and saved to ~/.bashrc"
    else
        echo "  ⏭️  Skipped. Set HF_TOKEN before training."
    fi
else
    huggingface-cli login --token "$HF_TOKEN"
    echo "  ✓ Already authenticated with HF_TOKEN"
fi

# 4. Run preflight check
echo ""
echo "🔍 Step 4: Preflight check..."
cd /workspace/mint
python scripts/runpod_preflight.py

echo ""
echo "=============================================="
echo "  ✅ SETUP COMPLETE"
echo "=============================================="
echo ""
echo "  Next steps:"
echo "    cd /workspace/mint"
echo ""
echo "  To verify LoRA is working:"
echo "    python scripts/verify_lora.py"
echo ""
echo "  To run industry evaluation:"
echo "    python scripts/evaluate_industry.py --model raghavenderreddy1212/mintai-v2 --samples 50"
echo ""
echo "  To run full train+eval+fix pipeline:"
echo "    python scripts/train_eval_fix_pipeline.py"
echo ""
echo "  To scrape more data first:"
echo "    export GITHUB_TOKEN='ghp_your_github_token'"
echo "    cd scrapers && ./run_pipeline.sh"
