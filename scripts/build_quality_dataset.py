"""
MINT — Build high-quality training dataset with validation and cleaning.

Steps:
1. Parse all sources (local repos + GitHub scrape)
2. Validate XML/DWL syntax
3. Generate structured instruction/output pairs
4. Clean: remove short, deduplicate, validate
5. Split train/test (80/20)

Output:
  data/dataset_train.jsonl
  data/dataset_test.jsonl
  data/dataset_stats.json
"""

import json
import hashlib
import re
from pathlib import Path
from xml.etree import ElementTree as ET

PROJECTS_DIR = Path("/Users/Raghavender/code-base-repo/mulesoft_projects")
SCRAPED_DIR = Path("/Users/Raghavender/lang-chain/mint/data/raw")
OUTPUT_DIR = Path("/Users/Raghavender/lang-chain/mint/data")

MIN_OUTPUT_TOKENS = 50  # minimum output length (chars as proxy for tokens)
MAX_OUTPUT_TOKENS = 8000  # maximum output length


def validate_xml(content: str) -> bool:
    """Check if XML is valid."""
    try:
        ET.fromstring(content)
        return True
    except ET.ParseError:
        # Try wrapping in a root element (partial XML)
        try:
            ET.fromstring(f"<root>{content}</root>")
            return True
        except:
            return False


def validate_dataweave(content: str) -> bool:
    """Basic DataWeave syntax validation."""
    # Must have %dw header or be a valid expression
    if "%dw" in content:
        return True
    # Simple expressions are also valid
    if content.strip().startswith("{") or content.strip().startswith("["):
        return True
    if "---" in content:
        return True
    return len(content.strip()) > 10


def extract_flow_instruction(xml_content: str, filename: str, app_name: str, func_doc: str = "") -> str:
    """Generate a natural instruction from a flow's content."""
    # Extract what the flow does
    connectors = set()
    operations = []

    connector_map = {
        "http:listener": "HTTP Listener",
        "http:request": "HTTP Request",
        "salesforce:create": "Salesforce Create",
        "salesforce:query": "Salesforce Query",
        "salesforce:update": "Salesforce Update",
        "db:select": "Database Select",
        "db:insert": "Database Insert",
        "kafka:publish": "Kafka Publish",
        "kafka:consumer": "Kafka Consumer",
        "ee:transform": "DataWeave Transform",
        "s3:put-object": "S3 Upload",
        "s3:get-object": "S3 Download",
        "email:send": "Send Email",
        "file:read": "File Read",
        "file:write": "File Write",
        "batch:job": "Batch Processing",
        "scatter-gather": "Scatter-Gather (parallel)",
        "choice": "Choice Router (conditional)",
        "try": "Error Handling",
        "foreach": "For Each Loop",
        "until-successful": "Retry Logic",
    }

    for pattern, label in connector_map.items():
        if pattern in xml_content:
            connectors.add(label)

    # Flow names
    flow_names = re.findall(r'<flow\s+name="([^"]+)"', xml_content)
    subflow_names = re.findall(r'<sub-flow\s+name="([^"]+)"', xml_content)

    # HTTP paths
    paths = re.findall(r'path="(/[^"]*)"', xml_content)

    # Build instruction
    parts = []

    if func_doc:
        parts.append(func_doc[:150])
    elif flow_names:
        clean_name = flow_names[0].replace("-", " ").replace("_", " ")
        parts.append(f"Create a Mule 4 flow named '{flow_names[0]}'")

    if connectors:
        parts.append(f"using {', '.join(sorted(connectors))}")

    if paths:
        parts.append(f"with API endpoint {paths[0]}")

    if not parts:
        parts.append(f"Create a Mule 4 flow from file '{filename}' in project '{app_name}'")

    return " ".join(parts)


def extract_dwl_instruction(content: str, filename: str) -> str:
    """Generate instruction from DataWeave content."""
    name_clean = filename.replace(".dwl", "").replace("-", " ").replace("_", " ")

    # Try to infer what it does
    indicators = []
    if "map" in content.lower():
        indicators.append("mapping/transformation")
    if "filter" in content.lower():
        indicators.append("filtering")
    if "groupBy" in content.lower():
        indicators.append("grouping")
    if "reduce" in content.lower():
        indicators.append("aggregation")
    if "xml" in content.lower() or "<" in content:
        indicators.append("XML handling")
    if "csv" in content.lower():
        indicators.append("CSV processing")
    if "flatten" in content.lower():
        indicators.append("flattening nested data")

    if indicators:
        return f"Write a DataWeave transformation for {name_clean} ({', '.join(indicators)})"
    return f"Write a DataWeave transformation: {name_clean}"


def process_local_projects() -> list[dict]:
    """Process your 132 local MuleSoft projects."""
    pairs = []

    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue

        app_name = project_dir.name

        # Read functional doc
        func_doc = ""
        for doc_name in ["Functional_Document.md", "README.md"]:
            doc_path = project_dir / doc_name
            if doc_path.exists():
                text = doc_path.read_text(encoding="utf-8", errors="ignore")
                for line in text.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("|") and len(line) > 30:
                        func_doc = line[:200]
                        break
                break

        # XML flows
        for xml_file in project_dir.rglob("src/main/mule/*.xml"):
            content = xml_file.read_text(encoding="utf-8", errors="ignore")
            if not validate_xml(content):
                continue
            if len(content) < MIN_OUTPUT_TOKENS or len(content) > MAX_OUTPUT_TOKENS:
                continue

            instruction = extract_flow_instruction(content, xml_file.name, app_name, func_doc)
            pairs.append({
                "instruction": instruction,
                "output": content.strip(),
                "metadata": {"source": "local", "app": app_name, "file": xml_file.name, "type": "flow"},
            })

        # DataWeave
        for dwl_file in project_dir.rglob("*.dwl"):
            content = dwl_file.read_text(encoding="utf-8", errors="ignore")
            if not validate_dataweave(content):
                continue
            if len(content) < MIN_OUTPUT_TOKENS or len(content) > MAX_OUTPUT_TOKENS:
                continue

            instruction = extract_dwl_instruction(content, dwl_file.name)
            pairs.append({
                "instruction": instruction,
                "output": content.strip(),
                "metadata": {"source": "local", "app": app_name, "file": dwl_file.name, "type": "dataweave"},
            })

    return pairs


def process_scraped_github() -> list[dict]:
    """Process scraped GitHub files."""
    pairs = []

    # Flows
    flows_dir = SCRAPED_DIR / "flows"
    if flows_dir.exists():
        for xml_file in sorted(flows_dir.glob("*.xml")):
            content = xml_file.read_text(encoding="utf-8", errors="ignore")
            if not validate_xml(content):
                continue
            if len(content) < MIN_OUTPUT_TOKENS or len(content) > MAX_OUTPUT_TOKENS:
                continue

            name_parts = xml_file.stem.split("_", 1)
            app_name = name_parts[0] if len(name_parts) > 1 else "github"
            instruction = extract_flow_instruction(content, xml_file.name, app_name)
            pairs.append({
                "instruction": instruction,
                "output": content.strip(),
                "metadata": {"source": "github", "file": xml_file.name, "type": "flow"},
            })

    # DataWeave
    dwl_dir = SCRAPED_DIR / "dataweave"
    if dwl_dir.exists():
        for dwl_file in sorted(dwl_dir.glob("*.dwl")):
            content = dwl_file.read_text(encoding="utf-8", errors="ignore")
            if not validate_dataweave(content):
                continue
            if len(content) < MIN_OUTPUT_TOKENS or len(content) > MAX_OUTPUT_TOKENS:
                continue

            instruction = extract_dwl_instruction(content, dwl_file.name)
            pairs.append({
                "instruction": instruction,
                "output": content.strip(),
                "metadata": {"source": "github", "file": dwl_file.name, "type": "dataweave"},
            })

    return pairs


def deduplicate(pairs: list[dict]) -> list[dict]:
    """Remove duplicates by hashing the output."""
    seen = set()
    unique = []
    for pair in pairs:
        h = hashlib.md5(pair["output"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(pair)
    return unique


def split_train_test(pairs: list[dict], test_ratio: float = 0.2) -> tuple[list, list]:
    """Split into train/test sets."""
    import random
    random.seed(42)
    shuffled = pairs.copy()
    random.shuffle(shuffled)
    split_idx = int(len(shuffled) * (1 - test_ratio))
    return shuffled[:split_idx], shuffled[split_idx:]


def main():
    print("MINT — Building Quality Training Dataset")
    print("=" * 60)

    # Step 1: Extract from all sources
    print("\n[1/5] Extracting from local projects...")
    local_pairs = process_local_projects()
    print(f"  Local: {len(local_pairs)} pairs")

    print("\n[2/5] Extracting from GitHub scrape...")
    github_pairs = process_scraped_github()
    print(f"  GitHub: {len(github_pairs)} pairs")

    all_pairs = local_pairs + github_pairs
    print(f"\n  Total raw: {len(all_pairs)}")

    # Step 2: Validate and filter
    print("\n[3/5] Validating and filtering...")
    valid_pairs = [p for p in all_pairs if len(p["output"]) >= MIN_OUTPUT_TOKENS]
    print(f"  After min length filter: {len(valid_pairs)}")

    # Step 3: Deduplicate
    print("\n[4/5] Deduplicating...")
    unique_pairs = deduplicate(valid_pairs)
    print(f"  After dedup: {len(unique_pairs)} (removed {len(valid_pairs) - len(unique_pairs)} duplicates)")

    # Step 4: Split
    print("\n[5/5] Splitting train/test (80/20)...")
    train, test = split_train_test(unique_pairs)
    print(f"  Train: {len(train)}")
    print(f"  Test:  {len(test)}")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    train_path = OUTPUT_DIR / "dataset_train.jsonl"
    test_path = OUTPUT_DIR / "dataset_test.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for item in train:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(test_path, "w", encoding="utf-8") as f:
        for item in test:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Stats
    stats = {
        "total_raw": len(all_pairs),
        "after_validation": len(valid_pairs),
        "after_dedup": len(unique_pairs),
        "train": len(train),
        "test": len(test),
        "by_type": {
            "flow": sum(1 for p in unique_pairs if p["metadata"]["type"] == "flow"),
            "dataweave": sum(1 for p in unique_pairs if p["metadata"]["type"] == "dataweave"),
        },
        "by_source": {
            "local": sum(1 for p in unique_pairs if p["metadata"]["source"] == "local"),
            "github": sum(1 for p in unique_pairs if p["metadata"]["source"] == "github"),
        },
    }

    (OUTPUT_DIR / "dataset_stats.json").write_text(json.dumps(stats, indent=2))

    print(f"\n{'=' * 60}")
    print("DATASET READY")
    print(f"{'=' * 60}")
    print(f"  Train: {train_path} ({train_path.stat().st_size / 1e6:.1f} MB)")
    print(f"  Test:  {test_path} ({test_path.stat().st_size / 1e6:.1f} MB)")
    print(f"  Stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    main()
