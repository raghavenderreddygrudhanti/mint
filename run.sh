#!/bin/bash
# ============================================================
# MINT — Single Command Full Pipeline
# ============================================================
# ONE COMMAND to rule them all. Run on RunPod:
#
#   curl -sSL https://raw.githubusercontent.com/raghavenderreddygrudhanti/mint/v3-pipeline/run.sh | bash
#
# Or if already cloned:
#   HF_TOKEN="hf_your_token" ./run.sh
# ============================================================

set -e

echo "╔══════════════════════════════════════════════╗"
echo "║     MINT v3 — Automated Training Pipeline   ║"
echo "╚══════════════════════════════════════════════╝"

# ============================================================
# STEP 0: HF Token
# ============================================================
if [ -z "$HF_TOKEN" ]; then
    echo ""
    echo "❌ HF_TOKEN not set!"
    echo ""
    echo "Run with:"
    echo "  HF_TOKEN=\"hf_your_token\" ./run.sh"
    echo ""
    echo "Get token: https://huggingface.co/settings/tokens (needs Write access)"
    exit 1
fi

echo ""
echo "🔑 [1/8] Authenticating with HuggingFace..."
pip install -q huggingface_hub 2>/dev/null
python -c "from huggingface_hub import HfApi; api=HfApi(token='$HF_TOKEN'); print(f'  ✓ Logged in as: {api.whoami()[\"name\"]}')"
export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"

# ============================================================
# STEP 1: Clone repo
# ============================================================
echo ""
echo "📦 [2/8] Setting up workspace..."
if [ ! -d "/workspace/mint" ]; then
    git clone -q --branch v3-pipeline https://github.com/raghavenderreddygrudhanti/mint.git /workspace/mint
fi
cd /workspace/mint
git pull -q origin v3-pipeline 2>/dev/null || true
echo "  ✓ Repo ready"

# ============================================================
# STEP 2: Install packages
# ============================================================
echo ""
echo "📦 [3/8] Installing packages..."
pip install -q unsloth trl datasets peft transformers accelerate bitsandbytes 2>&1 | tail -1
pip install -q huggingface_hub chromadb sentence-transformers numpy 2>&1 | tail -1
pip install -q requests beautifulsoup4 lxml tqdm tenacity 2>&1 | tail -1
echo "  ✓ All packages installed"

# ============================================================
# STEP 3: GPU check
# ============================================================
echo ""
echo "🖥️  [4/8] Checking GPU..."
python -c "
import torch
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f'  ✓ GPU: {name} ({mem:.0f}GB)')
else:
    print('  ✗ No GPU! Exiting.')
    exit(1)
"

# ============================================================
# STEP 4: Login to HF CLI
# ============================================================
echo ""
echo "🔐 [5/8] HuggingFace CLI login..."
huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential 2>/dev/null
echo "  ✓ CLI authenticated"

# ============================================================
# STEP 5: Verify LoRA works
# ============================================================
echo ""
echo "🧪 [6/8] Verifying LoRA adapter is working..."
python -c "
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

print('  Loading base + LoRA...')
tokenizer = AutoTokenizer.from_pretrained('raghavenderreddy1212/mintai-v2')
model = AutoModelForCausalLM.from_pretrained('unsloth/qwen2.5-coder-7b-instruct-bnb-4bit', torch_dtype=torch.float16, device_map='auto')
model = PeftModel.from_pretrained(model, 'raghavenderreddy1212/mintai-v2')
model.eval()

messages = [{'role':'system','content':'You are MINT, an expert MuleSoft developer.'},{'role':'user','content':'Create HTTP listener flow on port 8081'}]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors='pt').to(model.device)

with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=200, temperature=0.1, do_sample=True)
result = tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)

if '<mule' in result or 'http:listener' in result or '%dw' in result:
    print(f'  ✓ LoRA verified — generating MuleSoft code ({len(result)} chars)')
else:
    print(f'  ⚠️  Output may not be MuleSoft-specific. Continuing anyway...')

del model
torch.cuda.empty_cache()
"

# ============================================================
# STEP 6: Run industry evaluation (baseline)
# ============================================================
echo ""
echo "📊 [7/8] Running baseline evaluation..."
python scripts/evaluate_industry.py --model raghavenderreddy1212/mintai-v2 --samples 30

# ============================================================
# STEP 7: Train + Eval + Fix pipeline
# ============================================================
echo ""
echo "🚀 [8/8] Starting Train → Eval → Fix pipeline..."
echo "  (This pushes checkpoints to HuggingFace every 200 steps)"
echo ""
python scripts/train_eval_fix_pipeline.py

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║          ✅ PIPELINE COMPLETE                ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Results: data/eval/industry_scores.json"
echo "  Model:   https://huggingface.co/raghavenderreddy1212/mintai-v3-round1"
echo ""
