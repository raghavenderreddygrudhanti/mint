# MINT

**MuleSoft Intelligence — AI-powered code generation, analysis, and optimization for MuleSoft integrations.**

```bash
pip install mint-ai
```

```python
from mint import MINT

ai = MINT()

# Generate a complete Mule 4 flow
flow = ai.generate("HTTP listener that queries Salesforce Accounts and returns JSON")
print(flow)

# Analyze existing flow for issues
issues = ai.analyze("src/main/mule/my-flow.xml")
# → "Missing error handler on HTTP request"
# → "No timeout configured on Salesforce connector"

# Explain what a flow does
explanation = ai.explain("src/main/mule/complex-flow.xml")

# Generate DataWeave transformation
dwl = ai.dataweave("Transform input JSON {name, age} to XML <person><name/><age/></person>")
```

## Features

- **Generate** — Create complete Mule 4 flows from natural language
- **Analyze** — Find bugs, missing error handlers, security issues
- **Explain** — Plain English explanation of complex flows
- **DataWeave** — Generate DWL transformations from descriptions
- **Convert** — Mule 3 → Mule 4 migration assistance

## Benchmark

| Tool | First-time success rate | MuleSoft-specific |
|---|---|---|
| GitHub Copilot | 32% | No |
| Cursor | 37% | No |
| MuleSoft Dev Agent | 25% | Yes |
| **MINT** | **TBD** | **Yes** |

## How it works

MINT is a domain-specific code model fine-tuned on 10,000+ MuleSoft flows, DataWeave transforms, and integration patterns scraped from open-source repositories.

Architecture:
- Base: Qwen2.5-Coder-7B (open source)
- Fine-tuning: LoRA on MuleSoft-specific instruction pairs
- RAG: Bitcache vector store with MuleSoft documentation
- Evaluation: MuleBench (80-task benchmark)

## License

MIT
