"""
MINT Data Pipeline #5: Merge, Deduplicate & Prepare Training Data
==================================================================
Combines all scraped data, deduplicates, validates, and creates
the final training dataset.

Usage:
    python 05_merge_and_dedup.py

Input: data/scraped/*.jsonl + data/training.jsonl (existing)
Output: data/training_merged.jsonl (ready for fine-tuning)
"""

import json
import hashlib
import re
import logging
from pathlib import Path
from collections import Counter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
SCRAPED_DIR = DATA_DIR / "scraped"
OUTPUT_FILE = DATA_DIR / "training_merged.jsonl"
STATS_FILE = DATA_DIR / "merged_stats.json"


def normalize_xml(xml_str: str) -> str:
    """Normalize XML for deduplication (remove whitespace variations)."""
    # Remove XML comments
    xml_str = re.sub(r"<!--.*?-->", "", xml_str, flags=re.DOTALL)
    # Normalize whitespace
    xml_str = re.sub(r"\s+", " ", xml_str)
    # Remove doc:id attributes (they're unique per instance)
    xml_str = re.sub(r'doc:id="[^"]*"', "", xml_str)
    return xml_str.strip()


def normalize_dwl(dwl_str: str) -> str:
    """Normalize DataWeave for deduplication."""
    # Remove comments
    dwl_str = re.sub(r"//.*$", "", dwl_str, flags=re.MULTILINE)
    dwl_str = re.sub(r"/\*.*?\*/", "", dwl_str, flags=re.DOTALL)
    # Normalize whitespace
    dwl_str = re.sub(r"\s+", " ", dwl_str)
    return dwl_str.strip()


def content_hash(content: str, content_type: str) -> str:
    """Generate a normalized hash for deduplication."""
    if content_type == "flow":
        normalized = normalize_xml(content)
    elif content_type == "dataweave":
        normalized = normalize_dwl(content)
    else:
        normalized = re.sub(r"\s+", " ", content).strip()

    return hashlib.md5(normalized.encode()).hexdigest()


def validate_mule_xml(content: str) -> bool:
    """Validate that content is proper Mule 4 XML."""
    required = ["<mule ", "mulesoft.org/schema/mule"]
    has_required = any(r in content for r in required)

    # Must have at least one flow or sub-flow or config
    has_structure = any(s in content for s in [
        "<flow ", "<sub-flow ", "<http:listener-config",
        "<configuration-properties", "apikit:config",
        "<kafka:consumer-config", "<kafka:producer-config",
        "<db:config", "<salesforce:config", "<sap:config",
    ])

    # Not too short
    is_substantial = len(content) > 150

    return has_required and (has_structure or is_substantial)


def validate_dataweave(content: str) -> bool:
    """Validate that content is proper DataWeave."""
    content = content.strip()

    # Must start with %dw or contain it
    has_header = "%dw 2.0" in content or "%dw 2." in content or content.startswith("%dw")

    # Must have output declaration or be a function
    has_output = "output " in content or "fun " in content or "var " in content

    # Not too short
    is_substantial = len(content) > 30

    return (has_header or has_output) and is_substantial


def clean_instruction(instruction: str) -> str:
    """Clean up instruction text."""
    # Remove excessive whitespace
    instruction = re.sub(r"\s+", " ", instruction).strip()
    # Truncate very long instructions
    if len(instruction) > 500:
        instruction = instruction[:497] + "..."
    # Ensure it ends with proper punctuation
    if instruction and instruction[-1] not in ".!?":
        instruction += "."
    return instruction


def load_existing_data() -> list:
    """Load existing training data."""
    pairs = []
    existing_file = DATA_DIR / "training.jsonl"
    if existing_file.exists():
        with open(existing_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        pairs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    logger.info(f"Loaded {len(pairs)} existing training pairs")
    return pairs


def load_scraped_data() -> list:
    """Load all scraped data files."""
    pairs = []
    if not SCRAPED_DIR.exists():
        logger.warning(f"Scraped directory not found: {SCRAPED_DIR}")
        return pairs

    for jsonl_file in sorted(SCRAPED_DIR.glob("*.jsonl")):
        count = 0
        with open(jsonl_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        pairs.append(json.loads(line))
                        count += 1
                    except json.JSONDecodeError:
                        continue
        logger.info(f"  Loaded {count} pairs from {jsonl_file.name}")

    return pairs


def main():
    logger.info("Loading data sources...")

    # Load existing
    existing = load_existing_data()

    # Load scraped
    scraped = load_scraped_data()

    # Combine
    all_pairs = existing + scraped
    logger.info(f"Total raw pairs: {len(all_pairs)}")

    # Deduplicate
    seen_hashes = set()
    unique_pairs = []
    duplicate_count = 0

    for pair in all_pairs:
        output = pair.get("output", "")
        pair_type = pair.get("metadata", {}).get("type", "flow")

        h = content_hash(output, pair_type)
        if h in seen_hashes:
            duplicate_count += 1
            continue
        seen_hashes.add(h)
        unique_pairs.append(pair)

    logger.info(f"After deduplication: {len(unique_pairs)} (removed {duplicate_count} duplicates)")

    # Validate
    valid_pairs = []
    invalid_count = 0

    for pair in unique_pairs:
        output = pair.get("output", "")
        pair_type = pair.get("metadata", {}).get("type", "flow")

        if pair_type == "flow":
            if validate_mule_xml(output):
                valid_pairs.append(pair)
            else:
                invalid_count += 1
        elif pair_type == "dataweave":
            if validate_dataweave(output):
                valid_pairs.append(pair)
            else:
                invalid_count += 1
        else:
            valid_pairs.append(pair)

    logger.info(f"After validation: {len(valid_pairs)} (removed {invalid_count} invalid)")

    # Clean instructions
    for pair in valid_pairs:
        pair["instruction"] = clean_instruction(pair.get("instruction", ""))

    # Remove pairs with empty instructions or outputs
    valid_pairs = [
        p for p in valid_pairs
        if p.get("instruction") and p.get("output") and len(p["output"]) > 30
    ]
    logger.info(f"After cleanup: {len(valid_pairs)}")

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        for pair in valid_pairs:
            f.write(json.dumps(pair) + "\n")

    # Statistics
    type_counts = Counter(p.get("metadata", {}).get("type", "unknown") for p in valid_pairs)
    source_counts = Counter(p.get("metadata", {}).get("source", "unknown") for p in valid_pairs)

    stats = {
        "total_raw": len(all_pairs),
        "after_dedup": len(unique_pairs),
        "after_validation": len(valid_pairs),
        "duplicates_removed": duplicate_count,
        "invalid_removed": invalid_count,
        "by_type": dict(type_counts),
        "by_source": dict(source_counts),
    }

    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

    # Print summary
    logger.info(f"\n{'='*50}")
    logger.info(f"MERGE & DEDUP COMPLETE")
    logger.info(f"{'='*50}")
    logger.info(f"Final dataset: {len(valid_pairs)} pairs")
    logger.info(f"  By type: {dict(type_counts)}")
    logger.info(f"  By source: {dict(source_counts)}")
    logger.info(f"Output: {OUTPUT_FILE}")
    logger.info(f"Stats: {STATS_FILE}")


if __name__ == "__main__":
    main()
