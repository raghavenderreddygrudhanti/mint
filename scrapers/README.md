# MINT Training Data Pipeline

Scrapers to collect 10K+ MuleSoft training pairs for fine-tuning MINT, plus RAG documents for retrieval-augmented generation.

## Architecture: Fine-Tune + RAG Hybrid

```
┌─────────────────────────────────────────────────────────────┐
│                    MINT Inference Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User Query ──► RAG Retrieval ──► Augmented Prompt ──► MINT │
│                      │                    │            Model  │
│                      ▼                    ▼              │    │
│              Vector DB              "Context: ..."       │    │
│           (rag_documents)           + user query        ▼    │
│                                                    Generated │
│                                                    Mule 4    │
│                                                    Code      │
└─────────────────────────────────────────────────────────────┘
```

**Fine-tuned model** = Knows HOW to write Mule 4 XML/DataWeave (syntax, patterns, structure)
**RAG** = Knows WHAT to write about (connector configs, API details, version-specific info)

## Pipeline Steps

| Script | Source | What it collects | Expected yield |
|--------|--------|-----------------|----------------|
| `01_github_mule4_scraper.py` | GitHub | Mule 4 XML flows + DataWeave from `mulesoft-catalyst`, `mulesoft-consulting`, and search | 4,000-6,000 pairs |
| `02_mulesoft_docs_scraper.py` | docs.mulesoft.com | DataWeave cookbook, connector examples, runtime patterns | 1,500-2,500 pairs |
| `04_rag_docs_scraper.py` | docs.mulesoft.com | Full documentation text chunked for vector DB | 5,000+ chunks |
| `05_merge_and_dedup.py` | All sources | Merge, deduplicate, validate, clean | Final dataset |

## Quick Start

```bash
# 1. Set GitHub token (required for GitHub scraper)
export GITHUB_TOKEN="ghp_your_token_here"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run full pipeline
./run_pipeline.sh

# Or run individual scrapers:
python 01_github_mule4_scraper.py
python 02_mulesoft_docs_scraper.py
python 04_rag_docs_scraper.py
python 05_merge_and_dedup.py
```

## Output Files

```
data/
├── scraped/
│   ├── github_mule4_pairs.jsonl      # From GitHub repos
│   └── mulesoft_docs_pairs.jsonl     # From official docs
├── rag/
│   └── rag_documents.jsonl           # Chunked docs for vector DB
├── training_merged.jsonl             # Final training dataset (fine-tuning)
└── merged_stats.json                 # Dataset statistics
```

## Training Data Format

Each pair in `training_merged.jsonl`:
```json
{
  "instruction": "Create a MuleSoft 4 flow using Kafka connector for event publishing with error handling.",
  "output": "<?xml version=\"1.0\" ...><mule ...>...</mule>",
  "metadata": {
    "project": "mulesoft-catalyst/some-template",
    "file": "src/main/mule/implementation.xml",
    "type": "flow",
    "source": "github"
  }
}
```

## RAG Document Format

Each chunk in `rag_documents.jsonl`:
```json
{
  "id": "abc123...",
  "text": "The SAP Connector enables integration with SAP systems via RFC, BAPI, and IDoc...",
  "metadata": {
    "source": "docs.mulesoft.com",
    "url": "https://docs.mulesoft.com/sap-connector/latest/",
    "section": "connectors-sap",
    "heading": "SAP Connector Overview",
    "has_code": true
  }
}
```

## GitHub Token

Create a personal access token at https://github.com/settings/tokens with `public_repo` scope.
The scraper respects rate limits and will pause automatically when needed.

## No-Overlap Strategy

The pipeline avoids duplicates through:
1. **Content hashing** — MD5 of normalized content (removes whitespace, doc:ids)
2. **Cross-source dedup** — Merges existing training data with new scraped data
3. **Validation** — Rejects malformed XML and incomplete DataWeave
