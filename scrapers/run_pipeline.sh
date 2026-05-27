#!/bin/bash
# ============================================================
# MINT Training Data Pipeline
# ============================================================
# Runs all scrapers in sequence, then merges and deduplicates.
#
# Prerequisites:
#   export GITHUB_TOKEN="your_github_personal_access_token"
#   pip install -r requirements.txt
#
# Usage:
#   chmod +x run_pipeline.sh
#   ./run_pipeline.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "  MINT Training Data Pipeline"
echo "=============================================="
echo ""

# Check prerequisites
if [ -z "$GITHUB_TOKEN" ]; then
    echo "⚠️  WARNING: GITHUB_TOKEN not set!"
    echo "   GitHub scraper will be limited without it."
    echo "   Get one at: https://github.com/settings/tokens"
    echo ""
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "=============================================="
echo "  Step 1: GitHub Mule 4 Scraper"
echo "  (mulesoft-catalyst, mulesoft-consulting, + search)"
echo "=============================================="
python 01_github_mule4_scraper.py

echo ""
echo "=============================================="
echo "  Step 2: MuleSoft Docs Scraper"
echo "  (DataWeave cookbook, connector examples, runtime)"
echo "=============================================="
python 02_mulesoft_docs_scraper.py

echo ""
echo "=============================================="
echo "  Step 3: RAG Knowledge Base Builder"
echo "  (Full docs for vector DB indexing)"
echo "=============================================="
python 04_rag_docs_scraper.py

echo ""
echo "=============================================="
echo "  Step 4: Merge & Deduplicate"
echo "  (Combine all sources, validate, clean)"
echo "=============================================="
python 05_merge_and_dedup.py

echo ""
echo "=============================================="
echo "  ✅ PIPELINE COMPLETE"
echo "=============================================="
echo ""
echo "Training data: data/training_merged.jsonl"
echo "RAG documents: data/rag/rag_documents.jsonl"
echo "Statistics:    data/merged_stats.json"
echo ""
echo "Next steps:"
echo "  1. Fine-tune: Use training_merged.jsonl with your LoRA training script"
echo "  2. RAG index: Embed rag_documents.jsonl into ChromaDB/Qdrant"
echo "  3. Inference: RAG retrieves context → inject into prompt → model generates code"
