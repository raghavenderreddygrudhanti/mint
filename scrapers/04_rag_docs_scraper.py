"""
MINT Data Scraper #4: RAG Knowledge Base Builder
=================================================
Scrapes MuleSoft documentation for RAG indexing (NOT for fine-tuning).
This creates chunked text documents that get embedded and stored in a vector DB.

Sources:
- docs.mulesoft.com (all connector docs, runtime docs, DataWeave reference)
- MuleSoft developer tutorials
- RAML/OAS API specs from GitHub

Usage:
    python 04_rag_docs_scraper.py

Output: JSONL with chunked documents for embedding
"""

import json
import time
import re
import hashlib
import logging
from pathlib import Path
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "rag"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "rag_documents.jsonl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

seen_urls = set()
CHUNK_SIZE = 1000  # characters per chunk
CHUNK_OVERLAP = 200

# ============================================================
# Documentation Sitemap — All pages to scrape for RAG
# ============================================================
DOC_SECTIONS = {
    "mule-runtime": {
        "base": "https://docs.mulesoft.com/mule-runtime/latest/",
        "pages": [
            "about-mule-runtime",
            "mule-app-dev",
            "mule-application-about",
            "global-elements",
            "about-flows",
            "about-event-source",
            "about-event-processors",
            "about-components",
            "error-handling",
            "on-error-scope-concept",
            "try-scope-concept",
            "raise-error-component-reference",
            "choice-router-concept",
            "scatter-gather-concept",
            "for-each-scope-concept",
            "until-successful-scope",
            "first-successful",
            "round-robin",
            "async-scope-reference",
            "batch-processing-concept",
            "batch-job-concept",
            "batch-filters-and-batch-aggregator",
            "reliability-patterns",
            "transaction-management",
            "xa-transactions",
            "scheduler-concept",
            "flowref-about",
            "logger-component-reference",
            "set-payload-transformer-reference",
            "variable-transformer-reference",
            "remove-variable",
            "parse-template-reference",
            "transform-component-about",
            "cache-scope",
            "cryptography",
            "tls-configuration",
            "secure-configuration-properties",
            "mule-app-properties-to-configure",
            "configuring-properties",
            "shared-resources",
            "about-classloading-isolation",
            "mule-deployment-model",
        ],
    },
    "dataweave": {
        "base": "https://docs.mulesoft.com/dataweave/latest/",
        "pages": [
            "dataweave-quickstart",
            "dataweave-language-introduction",
            "dataweave-selectors",
            "dataweave-types",
            "dataweave-variables",
            "dataweave-flow-control",
            "dataweave-pattern-matching",
            "dw-operators",
            "dataweave-functions",
            "dataweave-functions-lambdas",
            "dw-core",
            "dw-core-functions-map",
            "dw-core-functions-mapobject",
            "dw-core-functions-filter",
            "dw-core-functions-reduce",
            "dw-core-functions-pluck",
            "dw-core-functions-flatten",
            "dw-core-functions-flatmap",
            "dw-core-functions-groupby",
            "dw-core-functions-orderby",
            "dw-core-functions-distinctby",
            "dw-core-functions-contains",
            "dw-core-functions-match",
            "dw-core-functions-replace",
            "dw-core-functions-splitby",
            "dw-core-functions-joinby",
            "dw-core-functions-zip",
            "dw-core-functions-unzip",
            "dw-core-functions-sizeof",
            "dw-core-functions-isempty",
            "dw-strings",
            "dw-arrays",
            "dw-objects",
            "dw-runtime",
            "dataweave-formats",
            "dataweave-formats-json",
            "dataweave-formats-xml",
            "dataweave-formats-csv",
            "dataweave-formats-java",
            "dataweave-formats-flatfile",
            "dataweave-formats-copybook",
            "dataweave-formats-multipart",
            "dataweave-formats-urlencoded",
        ],
    },
    "connectors-sap": {
        "base": "https://docs.mulesoft.com/sap-connector/latest/",
        "pages": [
            "",
            "sap-connector-examples",
            "sap-connector-config-topics",
            "sap-connector-send-idoc",
            "sap-connector-retrieve-idoc",
            "sap-connector-bapi-function",
            "sap-connector-reference",
        ],
    },
    "connectors-salesforce": {
        "base": "https://docs.mulesoft.com/salesforce-connector/latest/",
        "pages": [
            "",
            "salesforce-connector-examples",
            "salesforce-connector-config-topics",
            "salesforce-connector-processing-events",
            "salesforce-connector-xml-maven",
            "salesforce-connector-reference",
        ],
    },
    "connectors-db": {
        "base": "https://docs.mulesoft.com/db-connector/latest/",
        "pages": [
            "",
            "database-connector-examples-index",
            "database-connector-connection",
            "database-connector-select",
            "database-connector-insert-update-delete",
            "database-connector-bulk-operations",
            "database-connector-udt-stored-procedure",
            "database-connector-reference",
        ],
    },
    "connectors-http": {
        "base": "https://docs.mulesoft.com/http-connector/latest/",
        "pages": [
            "",
            "http-connector-examples",
            "http-start-app-brows-task",
            "http-load-static-res-task",
            "http-request-ref",
            "http-listener-ref",
            "http-authentication",
        ],
    },
    "connectors-kafka": {
        "base": "https://docs.mulesoft.com/kafka-connector/latest/",
        "pages": [
            "",
            "kafka-connector-examples",
            "kafka-connector-publish",
            "kafka-connector-consume",
            "kafka-connector-listener",
            "kafka-connector-reference",
        ],
    },
    "connectors-file": {
        "base": "https://docs.mulesoft.com/file-connector/latest/",
        "pages": [
            "",
            "file-examples",
            "file-read",
            "file-write",
            "file-list",
            "file-on-new-file",
            "file-copy-move",
        ],
    },
    "connectors-sftp": {
        "base": "https://docs.mulesoft.com/sftp-connector/latest/",
        "pages": [
            "",
            "sftp-examples",
            "sftp-read",
            "sftp-write",
            "sftp-list",
            "sftp-on-new-file",
            "sftp-copy-move",
        ],
    },
    "connectors-jms": {
        "base": "https://docs.mulesoft.com/jms-connector/latest/",
        "pages": [
            "",
            "jms-examples",
            "jms-publish",
            "jms-consume",
            "jms-listener",
            "jms-ack",
            "jms-transactions",
        ],
    },
    "connectors-vm": {
        "base": "https://docs.mulesoft.com/vm-connector/latest/",
        "pages": [
            "",
            "vm-examples",
            "vm-publish-listen",
            "vm-publish-response",
            "vm-dynamic-routing",
        ],
    },
    "connectors-objectstore": {
        "base": "https://docs.mulesoft.com/object-store-connector/latest/",
        "pages": [
            "",
            "object-store-connector-examples",
            "object-store-to-store-and-retrieve",
        ],
    },
    "connectors-email": {
        "base": "https://docs.mulesoft.com/email-connector/latest/",
        "pages": [
            "",
            "email-examples",
            "email-send",
            "email-list",
            "email-gmail",
        ],
    },
    "connectors-aws-s3": {
        "base": "https://docs.mulesoft.com/amazon-s3-connector/latest/",
        "pages": [
            "",
            "amazon-s3-connector-examples",
            "amazon-s3-connector-reference",
        ],
    },
    "connectors-aws-sqs": {
        "base": "https://docs.mulesoft.com/amazon-sqs-connector/latest/",
        "pages": [
            "",
            "amazon-sqs-connector-examples",
        ],
    },
    "connectors-dynamodb": {
        "base": "https://docs.mulesoft.com/amazon-dynamodb-connector/latest/",
        "pages": [
            "",
            "amazon-dynamodb-connector-examples",
        ],
    },
    "anypoint-mq": {
        "base": "https://docs.mulesoft.com/anypoint-mq-connector/latest/",
        "pages": [
            "",
            "anypoint-mq-connector-examples",
            "anypoint-mq-publish",
            "anypoint-mq-consume",
            "anypoint-mq-listener",
            "anypoint-mq-ack",
        ],
    },
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def fetch_page(url: str) -> Optional[str]:
    """Fetch a page with retries."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200:
        return r.text
    return None


def extract_text_content(html: str) -> dict:
    """Extract structured text content from a docs page."""
    soup = BeautifulSoup(html, "lxml")

    # Get title
    title = ""
    title_elem = soup.find("h1")
    if title_elem:
        title = title_elem.get_text(strip=True)

    # Remove nav, footer, sidebar
    for elem in soup.find_all(["nav", "footer", "aside", "header"]):
        elem.decompose()

    # Get main content area
    main = soup.find("main") or soup.find("article") or soup.find("div", class_="doc")
    if not main:
        main = soup.find("body")

    if not main:
        return {"title": title, "sections": []}

    # Extract sections by headers
    sections = []
    current_section = {"heading": title, "content": "", "code_blocks": []}

    for elem in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "code", "table"]):
        if elem.name in ["h1", "h2", "h3", "h4"]:
            if current_section["content"] or current_section["code_blocks"]:
                sections.append(current_section)
            current_section = {
                "heading": elem.get_text(strip=True),
                "content": "",
                "code_blocks": [],
            }
        elif elem.name in ["pre", "code"]:
            code_text = elem.get_text()
            if len(code_text) > 20:
                current_section["code_blocks"].append(code_text)
        elif elem.name == "table":
            # Extract table as text
            rows = []
            for row in elem.find_all("tr"):
                cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
                rows.append(" | ".join(cells))
            current_section["content"] += "\n" + "\n".join(rows) + "\n"
        else:
            text = elem.get_text(strip=True)
            if text:
                current_section["content"] += text + "\n"

    if current_section["content"] or current_section["code_blocks"]:
        sections.append(current_section)

    return {"title": title, "sections": sections}


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence end near the chunk boundary
            for sep in [". ", ".\n", "\n\n", "\n"]:
                last_sep = text.rfind(sep, start + chunk_size // 2, end + 100)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if len(c) > 50]


def process_page_for_rag(url: str, section_name: str) -> List[dict]:
    """Process a single documentation page into RAG chunks."""
    html = fetch_page(url)
    if not html:
        return []

    content = extract_text_content(html)
    documents = []

    for section in content["sections"]:
        # Combine text and code blocks
        full_text = section["content"]
        if section["code_blocks"]:
            full_text += "\n\nCode examples:\n"
            for code in section["code_blocks"]:
                full_text += f"\n```\n{code}\n```\n"

        if len(full_text.strip()) < 50:
            continue

        # Chunk the content
        chunks = chunk_text(full_text)

        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(f"{url}:{section['heading']}:{i}".encode()).hexdigest()

            documents.append({
                "id": doc_id,
                "text": chunk,
                "metadata": {
                    "source": "docs.mulesoft.com",
                    "url": url,
                    "section": section_name,
                    "heading": section["heading"],
                    "page_title": content["title"],
                    "chunk_index": i,
                    "has_code": bool(section["code_blocks"]),
                },
            })

    return documents


def scrape_github_readmes() -> List[dict]:
    """Scrape README files from MuleSoft GitHub orgs for RAG context."""
    documents = []
    github_token = __import__("os").environ.get("GITHUB_TOKEN", "")

    if not github_token:
        logger.warning("No GITHUB_TOKEN set. Skipping GitHub README scraping.")
        return documents

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    orgs = ["mulesoft-catalyst", "mulesoft-consulting"]

    for org in orgs:
        try:
            page = 1
            while page <= 5:
                url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"
                r = requests.get(url, headers=headers)
                if r.status_code != 200:
                    break
                repos = r.json()
                if not repos:
                    break

                for repo in repos:
                    # Get README
                    readme_url = f"https://api.github.com/repos/{repo['full_name']}/readme"
                    rr = requests.get(readme_url, headers=headers)
                    if rr.status_code == 200:
                        import base64
                        content = base64.b64decode(rr.json().get("content", "")).decode("utf-8", errors="ignore")
                        if len(content) > 100:
                            chunks = chunk_text(content)
                            for i, chunk in enumerate(chunks):
                                documents.append({
                                    "id": hashlib.md5(f"{repo['full_name']}:readme:{i}".encode()).hexdigest(),
                                    "text": chunk,
                                    "metadata": {
                                        "source": "github",
                                        "url": repo["html_url"],
                                        "section": "readme",
                                        "heading": repo["full_name"],
                                        "page_title": repo.get("description", ""),
                                        "chunk_index": i,
                                        "has_code": "```" in chunk or "<mule" in chunk,
                                    },
                                })
                    time.sleep(0.5)

                page += 1
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Failed to scrape {org} READMEs: {e}")

    return documents


def main():
    all_documents = []

    # Scrape all documentation sections
    for section_name, config in tqdm(DOC_SECTIONS.items(), desc="Doc sections"):
        base_url = config["base"]
        pages = config["pages"]

        for page_slug in pages:
            url = f"{base_url}{page_slug}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            docs = process_page_for_rag(url, section_name)
            all_documents.extend(docs)
            time.sleep(0.5)

        logger.info(f"  {section_name}: {len(all_documents)} total chunks so far")

    # Scrape GitHub READMEs for additional context
    logger.info("Scraping GitHub READMEs for RAG context...")
    readme_docs = scrape_github_readmes()
    all_documents.extend(readme_docs)
    logger.info(f"  Added {len(readme_docs)} README chunks")

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        for doc in all_documents:
            f.write(json.dumps(doc) + "\n")

    # Summary
    code_chunks = sum(1 for d in all_documents if d["metadata"].get("has_code"))

    logger.info(f"\n{'='*50}")
    logger.info(f"RAG KNOWLEDGE BASE COMPLETE")
    logger.info(f"{'='*50}")
    logger.info(f"Total chunks: {len(all_documents)}")
    logger.info(f"  With code: {code_chunks}")
    logger.info(f"  Text only: {len(all_documents) - code_chunks}")
    logger.info(f"Output: {OUTPUT_FILE}")
    logger.info(f"\nNext step: Embed these chunks and store in a vector DB")
    logger.info(f"  Recommended: ChromaDB, Qdrant, or Pinecone")


if __name__ == "__main__":
    main()
