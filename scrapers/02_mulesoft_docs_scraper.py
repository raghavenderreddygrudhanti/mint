"""
MINT Data Scraper #2: MuleSoft Official Documentation
======================================================
Scrapes docs.mulesoft.com for:
- DataWeave cookbook examples
- Connector examples (SAP, Salesforce, DB, Kafka, etc.)
- Mule runtime flow examples
- Error handling patterns

Usage:
    python 02_mulesoft_docs_scraper.py

Expected yield: 1,500-2,500 pairs
"""

import json
import time
import re
import hashlib
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "scraped"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "mulesoft_docs_pairs.jsonl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

seen_hashes = set()

# ============================================================
# DataWeave Cookbook URLs
# ============================================================
DATAWEAVE_COOKBOOK_PAGES = [
    "dataweave-cookbook-perform-basic-transformation",
    "dataweave-cookbook-map",
    "dataweave-cookbook-map-object",
    "dataweave-cookbook-map-an-object",
    "dataweave-cookbook-rename-keys",
    "dataweave-cookbook-output-a-field-when-present",
    "dataweave-cookbook-format-dates",
    "dataweave-cookbook-change-value-of-a-field",
    "dataweave-cookbook-exclude-field",
    "dataweave-cookbook-conditional-list-reduction-via-function",
    "dataweave-cookbook-define-function-that-flattens-list",
    "dataweave-cookbook-use-constant-directives",
    "dataweave-cookbook-pass-functions-as-arguments",
    "dataweave-cookbook-set-reader-writer-props",
    "dataweave-cookbook-insert-attribute",
    "dataweave-cookbook-remove-certain-xml-attributes",
    "dataweave-cookbook-include-xml-namespaces",
    "dataweave-cookbook-reference-multiple-inputs",
    "dataweave-cookbook-zip-arrays-together",
    "dataweave-cookbook-pick-top-elements",
    "dataweave-cookbook-regroup-fields",
    "dataweave-cookbook-merge-multiple-payloads",
    "dataweave-cookbook-use-constant-directives",
    "dataweave-cookbook-defaults",
    "dataweave-cookbook-extract-data",
    "dataweave-cookbook-add-and-subtract-time",
    "dataweave-cookbook-writer-prop-mule",
    "dataweave-cookbook-flatten-arrays",
    "dataweave-cookbook-java-methods",
    "dataweave-cookbook-select-xml-elements",
    "dataweave-cookbook-pattern-matching",
    "dataweave-cookbook-reduce",
    "dataweave-cookbook-filter",
    "dataweave-cookbook-pluck",
    "dataweave-cookbook-groupby",
    "dataweave-cookbook-orderby",
    "dataweave-cookbook-distinctby",
    "dataweave-cookbook-splitby",
    "dataweave-cookbook-joinby",
    "dataweave-cookbook-contains",
    "dataweave-cookbook-match",
    "dataweave-cookbook-replace",
    "dataweave-cookbook-type-coercion",
]

# ============================================================
# Connector Example Pages
# ============================================================
CONNECTOR_PAGES = {
    "SAP": [
        "https://docs.mulesoft.com/sap-connector/latest/sap-connector-examples",
        "https://docs.mulesoft.com/sap-connector/latest/sap-connector-config-topics",
        "https://docs.mulesoft.com/sap-s4hana-cloud-connector/latest/sap-s4hana-cloud-connector-examples",
        "https://docs.mulesoft.com/sap-s4hana-soap-connector/latest/sap-s4hana-soap-connector-examples",
    ],
    "Salesforce": [
        "https://docs.mulesoft.com/salesforce-connector/latest/salesforce-connector-examples",
        "https://docs.mulesoft.com/salesforce-connector/latest/salesforce-connector-xml-maven",
        "https://docs.mulesoft.com/salesforce-composite-connector/latest/salesforce-composite-connector-examples",
    ],
    "Database": [
        "https://docs.mulesoft.com/db-connector/latest/database-connector-examples-index",
        "https://docs.mulesoft.com/db-connector/latest/database-connector-select",
        "https://docs.mulesoft.com/db-connector/latest/database-connector-insert-update-delete",
        "https://docs.mulesoft.com/db-connector/latest/database-connector-udt-stored-procedure",
    ],
    "HTTP": [
        "https://docs.mulesoft.com/http-connector/latest/http-connector-examples",
        "https://docs.mulesoft.com/http-connector/latest/http-start-app-brows-task",
        "https://docs.mulesoft.com/http-connector/latest/http-load-static-res-task",
    ],
    "Kafka": [
        "https://docs.mulesoft.com/kafka-connector/latest/kafka-connector-examples",
    ],
    "File": [
        "https://docs.mulesoft.com/file-connector/latest/file-examples",
        "https://docs.mulesoft.com/file-connector/latest/file-read",
        "https://docs.mulesoft.com/file-connector/latest/file-write",
        "https://docs.mulesoft.com/file-connector/latest/file-list",
    ],
    "SFTP": [
        "https://docs.mulesoft.com/sftp-connector/latest/sftp-examples",
        "https://docs.mulesoft.com/sftp-connector/latest/sftp-read",
        "https://docs.mulesoft.com/sftp-connector/latest/sftp-write",
    ],
    "JMS": [
        "https://docs.mulesoft.com/jms-connector/latest/jms-examples",
        "https://docs.mulesoft.com/jms-connector/latest/jms-publish",
        "https://docs.mulesoft.com/jms-connector/latest/jms-consume",
        "https://docs.mulesoft.com/jms-connector/latest/jms-listener",
    ],
    "AMQP": [
        "https://docs.mulesoft.com/amqp-connector/latest/amqp-examples",
    ],
    "VM": [
        "https://docs.mulesoft.com/vm-connector/latest/vm-examples",
        "https://docs.mulesoft.com/vm-connector/latest/vm-publish-listen",
    ],
    "ObjectStore": [
        "https://docs.mulesoft.com/object-store-connector/latest/object-store-connector-examples",
    ],
    "Email": [
        "https://docs.mulesoft.com/email-connector/latest/email-examples",
        "https://docs.mulesoft.com/email-connector/latest/email-send",
    ],
    "Amazon S3": [
        "https://docs.mulesoft.com/amazon-s3-connector/latest/amazon-s3-connector-examples",
    ],
    "Amazon SQS": [
        "https://docs.mulesoft.com/amazon-sqs-connector/latest/amazon-sqs-connector-examples",
    ],
    "DynamoDB": [
        "https://docs.mulesoft.com/amazon-dynamodb-connector/latest/amazon-dynamodb-connector-examples",
    ],
}

# ============================================================
# Mule Runtime Pages (error handling, routing, scopes)
# ============================================================
MULE_RUNTIME_PAGES = [
    "https://docs.mulesoft.com/mule-runtime/latest/choice-router-concept",
    "https://docs.mulesoft.com/mule-runtime/latest/scatter-gather-concept",
    "https://docs.mulesoft.com/mule-runtime/latest/try-scope-concept",
    "https://docs.mulesoft.com/mule-runtime/latest/until-successful-scope",
    "https://docs.mulesoft.com/mule-runtime/latest/for-each-scope-concept",
    "https://docs.mulesoft.com/mule-runtime/latest/first-successful",
    "https://docs.mulesoft.com/mule-runtime/latest/round-robin",
    "https://docs.mulesoft.com/mule-runtime/latest/batch-processing-concept",
    "https://docs.mulesoft.com/mule-runtime/latest/error-handling",
    "https://docs.mulesoft.com/mule-runtime/latest/on-error-scope-concept",
    "https://docs.mulesoft.com/mule-runtime/latest/raise-error-component-reference",
    "https://docs.mulesoft.com/mule-runtime/latest/transform-component-about",
    "https://docs.mulesoft.com/mule-runtime/latest/flowref-about",
    "https://docs.mulesoft.com/mule-runtime/latest/async-scope-reference",
    "https://docs.mulesoft.com/mule-runtime/latest/scheduler-concept",
    "https://docs.mulesoft.com/mule-runtime/latest/logger-component-reference",
    "https://docs.mulesoft.com/mule-runtime/latest/set-payload-transformer-reference",
    "https://docs.mulesoft.com/mule-runtime/latest/variable-transformer-reference",
    "https://docs.mulesoft.com/mule-runtime/latest/cache-scope",
    "https://docs.mulesoft.com/mule-runtime/latest/reliability-patterns",
    "https://docs.mulesoft.com/mule-runtime/latest/transaction-management",
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def fetch_page(url: str) -> Optional[str]:
    """Fetch a documentation page."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200:
        return r.text
    return None


def extract_code_blocks(html: str) -> list:
    """Extract XML and DataWeave code blocks from HTML."""
    soup = BeautifulSoup(html, "lxml")
    blocks = []

    # Find all code blocks (pre > code, or div.listingblock)
    for code_elem in soup.find_all(["code", "pre"]):
        text = code_elem.get_text(strip=True)

        # Check if it's Mule XML
        if "<mule " in text or "<flow " in text or "mulesoft.org/schema" in text:
            blocks.append({"type": "flow", "content": text})

        # Check if it's DataWeave
        elif text.startswith("%dw") or "%dw 2.0" in text:
            blocks.append({"type": "dataweave", "content": text})

    # Also look for content in listingblock divs (Asciidoc format)
    for listing in soup.find_all("div", class_="listingblock"):
        content_div = listing.find("div", class_="content")
        if content_div:
            pre = content_div.find("pre")
            if pre:
                text = pre.get_text()
                if "<mule " in text or "<flow " in text:
                    blocks.append({"type": "flow", "content": text})
                elif "%dw 2.0" in text or text.strip().startswith("%dw"):
                    blocks.append({"type": "dataweave", "content": text})

    return blocks


def extract_page_context(html: str) -> str:
    """Extract the page title and description for instruction generation."""
    soup = BeautifulSoup(html, "lxml")

    title = ""
    title_elem = soup.find("h1") or soup.find("title")
    if title_elem:
        title = title_elem.get_text(strip=True)

    # Get first paragraph as description
    desc = ""
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) > 50:
            desc = text[:200]
            break

    return f"{title}. {desc}" if desc else title


def scrape_dataweave_cookbook():
    """Scrape DataWeave cookbook examples."""
    pairs = []
    base_url = "https://docs.mulesoft.com/dataweave/latest/"

    for page_slug in tqdm(DATAWEAVE_COOKBOOK_PAGES, desc="DataWeave Cookbook"):
        url = f"{base_url}{page_slug}"
        html = fetch_page(url)
        if not html:
            continue

        context = extract_page_context(html)
        blocks = extract_code_blocks(html)

        for block in blocks:
            content = block["content"]
            h = hashlib.md5(content.strip().encode()).hexdigest()
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            if len(content) < 30:
                continue

            if block["type"] == "dataweave":
                instruction = f"Write a DataWeave transformation: {context}"
            else:
                instruction = f"Create a MuleSoft 4 flow demonstrating: {context}"

            pairs.append({
                "instruction": instruction,
                "output": content,
                "metadata": {
                    "source": "docs.mulesoft.com",
                    "url": url,
                    "type": block["type"],
                    "category": "dataweave-cookbook",
                }
            })

        time.sleep(1)

    return pairs


def scrape_connector_examples():
    """Scrape connector example pages."""
    pairs = []

    for connector_name, urls in tqdm(CONNECTOR_PAGES.items(), desc="Connectors"):
        for url in urls:
            html = fetch_page(url)
            if not html:
                continue

            context = extract_page_context(html)
            blocks = extract_code_blocks(html)

            for block in blocks:
                content = block["content"]
                h = hashlib.md5(content.strip().encode()).hexdigest()
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)

                if len(content) < 50:
                    continue

                if block["type"] == "flow":
                    instruction = f"Create a MuleSoft 4 flow using {connector_name} connector: {context}"
                else:
                    instruction = f"Write a DataWeave transformation for {connector_name} integration: {context}"

                pairs.append({
                    "instruction": instruction,
                    "output": content,
                    "metadata": {
                        "source": "docs.mulesoft.com",
                        "url": url,
                        "type": block["type"],
                        "category": f"connector-{connector_name.lower()}",
                        "connector": connector_name,
                    }
                })

            time.sleep(1)

    return pairs


def scrape_mule_runtime():
    """Scrape Mule runtime component examples."""
    pairs = []

    for url in tqdm(MULE_RUNTIME_PAGES, desc="Mule Runtime"):
        html = fetch_page(url)
        if not html:
            continue

        context = extract_page_context(html)
        blocks = extract_code_blocks(html)

        for block in blocks:
            content = block["content"]
            h = hashlib.md5(content.strip().encode()).hexdigest()
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            if len(content) < 50:
                continue

            if block["type"] == "flow":
                instruction = f"Create a MuleSoft 4 flow demonstrating: {context}"
            else:
                instruction = f"Write a DataWeave transformation for: {context}"

            pairs.append({
                "instruction": instruction,
                "output": content,
                "metadata": {
                    "source": "docs.mulesoft.com",
                    "url": url,
                    "type": block["type"],
                    "category": "mule-runtime",
                }
            })

        time.sleep(1)

    return pairs


def main():
    all_pairs = []

    logger.info("Scraping DataWeave Cookbook...")
    all_pairs.extend(scrape_dataweave_cookbook())
    logger.info(f"  Collected: {len(all_pairs)} pairs")

    logger.info("Scraping Connector Examples...")
    connector_pairs = scrape_connector_examples()
    all_pairs.extend(connector_pairs)
    logger.info(f"  Collected: {len(all_pairs)} total pairs")

    logger.info("Scraping Mule Runtime Examples...")
    runtime_pairs = scrape_mule_runtime()
    all_pairs.extend(runtime_pairs)
    logger.info(f"  Collected: {len(all_pairs)} total pairs")

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        for pair in all_pairs:
            f.write(json.dumps(pair) + "\n")

    # Summary
    flow_count = sum(1 for p in all_pairs if p["metadata"]["type"] == "flow")
    dw_count = sum(1 for p in all_pairs if p["metadata"]["type"] == "dataweave")

    logger.info(f"\n{'='*50}")
    logger.info(f"DOCS SCRAPING COMPLETE")
    logger.info(f"{'='*50}")
    logger.info(f"Total pairs: {len(all_pairs)}")
    logger.info(f"  Flows: {flow_count}")
    logger.info(f"  DataWeave: {dw_count}")
    logger.info(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
