"""
MINT Data Scraper #1: GitHub Mule 4 Projects
=============================================
Scrapes public GitHub repos for Mule 4 XML flows and DataWeave (.dwl) files.
Targets: src/main/mule/*.xml and src/main/resources/**/*.dwl

Usage:
    export GITHUB_TOKEN="your_github_personal_access_token"
    python 01_github_mule4_scraper.py

Expected yield: 4,000-6,000 pairs
"""

import os
import json
import time
import base64
import hashlib
import logging
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "scraped"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "github_mule4_pairs.jsonl"

# Track hashes to avoid duplicates
seen_hashes = set()


def check_rate_limit():
    """Check GitHub API rate limit and sleep if needed."""
    r = requests.get("https://api.github.com/rate_limit", headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        remaining = data["resources"]["search"]["remaining"]
        reset_time = data["resources"]["search"]["reset"]
        if remaining < 5:
            wait = reset_time - time.time() + 5
            if wait > 0:
                logger.info(f"Rate limit low ({remaining}). Sleeping {wait:.0f}s...")
                time.sleep(wait)
        return remaining
    return 999


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
def github_search_repos(query: str, page: int = 1, per_page: int = 100) -> list:
    """Search GitHub for repositories matching query."""
    check_rate_limit()
    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "per_page": per_page,
        "page": page,
        "sort": "updated",
    }
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json().get("items", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
def github_search_code(query: str, page: int = 1, per_page: int = 100) -> list:
    """Search GitHub code."""
    check_rate_limit()
    url = "https://api.github.com/search/code"
    params = {"q": query, "per_page": per_page, "page": page}
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json().get("items", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def get_file_content(repo_full_name: str, path: str) -> Optional[str]:
    """Get raw file content from GitHub."""
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{path}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        if data.get("encoding") == "base64" and data.get("content"):
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def get_repo_tree(repo_full_name: str, branch: str = "main") -> list:
    """Get full file tree of a repo."""
    url = f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}?recursive=1"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json().get("tree", [])
    # Try master branch
    url = f"https://api.github.com/repos/{repo_full_name}/git/trees/master?recursive=1"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json().get("tree", [])
    return []


def is_mule4_xml(content: str) -> bool:
    """Check if content is a valid Mule 4 XML file."""
    indicators = [
        "http://www.mulesoft.org/schema/mule/core",
        "<mule ",
        "xmlns:ee=",
        "<flow ",
        "<sub-flow ",
        "mule-apikit",
    ]
    return any(ind in content for ind in indicators)


def is_dataweave(content: str) -> bool:
    """Check if content is a valid DataWeave file."""
    return content.strip().startswith("%dw") or "%dw 2.0" in content


def content_hash(content: str) -> str:
    """Generate hash for deduplication."""
    return hashlib.md5(content.strip().encode()).hexdigest()


def generate_instruction_for_flow(repo_name: str, filename: str, content: str) -> str:
    """Generate a natural instruction for a Mule flow."""
    # Extract connectors used
    connectors = []
    connector_map = {
        "http:": "HTTP",
        "salesforce:": "Salesforce",
        "kafka:": "Kafka",
        "db:": "Database",
        "sap:": "SAP",
        "sftp:": "SFTP",
        "ftp:": "FTP",
        "jms:": "JMS",
        "amqp:": "AMQP",
        "vm:": "VM",
        "file:": "File",
        "email:": "Email",
        "dynamodb:": "DynamoDB",
        "s3:": "Amazon S3",
        "sqs:": "Amazon SQS",
        "sns:": "Amazon SNS",
        "objectstore:": "Object Store",
        "os:": "Object Store",
        "batch:": "Batch",
        "scheduler": "Scheduler",
        "apikit:": "APIkit",
        "json-logger:": "JSON Logger",
        "ee:transform": "DataWeave Transform",
    }

    for key, name in connector_map.items():
        if key in content:
            connectors.append(name)

    # Extract flow names
    import re
    flow_names = re.findall(r'name="([^"]+)"', content[:500])

    project_clean = repo_name.split("/")[-1].replace("-", " ").replace("_", " ")

    parts = [f"Create a MuleSoft 4 flow for: {project_clean}."]
    if connectors:
        parts.append(f"Uses: {', '.join(set(connectors[:5]))}.")
    if flow_names:
        parts.append(f"Main flow: {flow_names[0]}.")

    return " ".join(parts)


def generate_instruction_for_dwl(repo_name: str, filename: str, content: str) -> str:
    """Generate a natural instruction for a DataWeave file."""
    import re

    project_clean = repo_name.split("/")[-1].replace("-", " ").replace("_", " ")
    file_clean = filename.replace(".dwl", "").replace("-", " ").replace("_", " ")

    # Detect output format
    output_match = re.search(r"output\s+(application/\w+)", content)
    output_format = output_match.group(1) if output_match else "application/json"

    # Detect functions used
    functions = []
    dw_functions = ["map", "filter", "reduce", "flatMap", "groupBy", "orderBy",
                    "distinctBy", "pluck", "mapObject", "flatten", "zip", "joinBy",
                    "splitBy", "contains", "match", "replace", "upper", "lower",
                    "trim", "now", "uuid"]
    for fn in dw_functions:
        if fn in content:
            functions.append(fn)

    parts = [f"Write a DataWeave transformation for: {file_clean}."]
    parts.append(f"Output format: {output_format}.")
    if functions:
        parts.append(f"Uses: {', '.join(functions[:5])}.")
    parts.append(f"Project: {project_clean}.")

    return " ".join(parts)


def scrape_repo(repo_full_name: str) -> list:
    """Scrape a single repo for Mule 4 files."""
    pairs = []
    tree = get_repo_tree(repo_full_name)

    if not tree:
        return pairs

    # Find Mule XML files
    mule_files = [
        f for f in tree
        if f["type"] == "blob" and (
            (f["path"].endswith(".xml") and "src/main/mule" in f["path"]) or
            (f["path"].endswith(".xml") and "mule" in f["path"].lower() and "test" not in f["path"].lower())
        )
    ]

    # Find DataWeave files
    dwl_files = [
        f for f in tree
        if f["type"] == "blob" and f["path"].endswith(".dwl")
    ]

    # Process XML files
    for file_info in mule_files[:20]:  # Limit per repo
        content = get_file_content(repo_full_name, file_info["path"])
        if not content or not is_mule4_xml(content):
            continue

        h = content_hash(content)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        # Skip very small or very large files
        if len(content) < 200 or len(content) > 50000:
            continue

        filename = file_info["path"].split("/")[-1]
        instruction = generate_instruction_for_flow(repo_full_name, filename, content)

        pairs.append({
            "instruction": instruction,
            "output": content,
            "metadata": {
                "project": repo_full_name,
                "file": file_info["path"],
                "type": "flow",
                "source": "github",
            }
        })
        time.sleep(0.5)

    # Process DataWeave files
    for file_info in dwl_files[:20]:  # Limit per repo
        content = get_file_content(repo_full_name, file_info["path"])
        if not content or not is_dataweave(content):
            continue

        h = content_hash(content)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        if len(content) < 30 or len(content) > 20000:
            continue

        filename = file_info["path"].split("/")[-1]
        instruction = generate_instruction_for_dwl(repo_full_name, filename, content)

        pairs.append({
            "instruction": instruction,
            "output": content,
            "metadata": {
                "project": repo_full_name,
                "file": file_info["path"],
                "type": "dataweave",
                "source": "github",
            }
        })
        time.sleep(0.5)

    return pairs


def main():
    if not GITHUB_TOKEN:
        logger.error("Set GITHUB_TOKEN environment variable!")
        logger.error("Create one at: https://github.com/settings/tokens")
        return

    # ============================================================
    # PRIORITY ORGS: Scrape ALL repos from these official orgs
    # ============================================================
    PRIORITY_ORGS = [
        "mulesoft-catalyst",      # Official templates & accelerators
        "mulesoft-consulting",    # Consulting team examples & skeletons
        "mulesoft",               # Core MuleSoft repos
        "manikmagar",            # Community contributor with mule4 examples
    ]

    # Search queries to find additional Mule 4 repos
    search_queries = [
        "mulesoft mule4",
        "mule 4 api",
        "mulesoft connector",
        "mule-maven-plugin",
        "mulesoft integration",
        "mule4 dataweave",
        "mulesoft salesforce",
        "mulesoft kafka",
        "mulesoft sap",
        "mulesoft api-led",
        "mule4 http listener",
        "mulesoft experience api",
        "mulesoft process api",
        "mulesoft system api",
        "anypoint mule4",
        "mulesoft enterprise",
        "mule4 error handling",
        "mulesoft batch processing",
        "mule4 scatter gather",
        "dataweave transformation",
        "mule4 template",
        "mulesoft accelerator",
        "mule4 skeleton",
        "mulesoft raml api",
    ]

    all_repos = set()

    # Phase 0: Get ALL repos from priority orgs
    logger.info("Phase 0: Scraping priority GitHub organizations...")
    for org in PRIORITY_ORGS:
        logger.info(f"  Fetching repos from: {org}")
        page = 1
        while True:
            try:
                check_rate_limit()
                url = f"https://api.github.com/orgs/{org}/repos"
                params = {"per_page": 100, "page": page, "type": "public"}
                r = requests.get(url, headers=HEADERS, params=params)
                if r.status_code != 200:
                    # Try as user instead of org
                    url = f"https://api.github.com/users/{org}/repos"
                    r = requests.get(url, headers=HEADERS, params=params)
                if r.status_code != 200:
                    break
                repos = r.json()
                if not repos:
                    break
                for repo in repos:
                    all_repos.add(repo["full_name"])
                page += 1
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to fetch {org} page {page}: {e}")
                break
        logger.info(f"    Found {len([r for r in all_repos if r.startswith(org)])} repos from {org}")

    logger.info(f"Priority orgs total: {len(all_repos)} repos")

    # Phase 1: Search for additional repos
    logger.info("Phase 1: Discovering additional Mule 4 repositories...")
    for query in tqdm(search_queries, desc="Searching"):
        for page in range(1, 6):  # 5 pages per query
            try:
                repos = github_search_repos(query, page=page)
                for repo in repos:
                    all_repos.add(repo["full_name"])
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Search failed for '{query}' page {page}: {e}")
                break

    logger.info(f"Found {len(all_repos)} unique repositories")

    # Also search directly for code
    logger.info("Phase 2: Direct code search for Mule XML...")
    code_queries = [
        "filename:*.xml mulesoft.org/schema/mule/core",
        "filename:*.dwl %dw 2.0 output",
        "path:src/main/mule extension:xml",
        "filename:global.xml http:listener-config",
        "filename:*.dwl mapObject",
        "filename:*.dwl flatMap",
    ]

    for query in tqdm(code_queries, desc="Code search"):
        for page in range(1, 4):
            try:
                items = github_search_code(query, page=page)
                for item in items:
                    all_repos.add(item["repository"]["full_name"])
                time.sleep(3)
            except Exception as e:
                logger.warning(f"Code search failed: {e}")
                break

    logger.info(f"Total unique repos after code search: {len(all_repos)}")

    # Scrape each repo
    all_pairs = []
    logger.info("Phase 3: Scraping repositories...")

    with open(OUTPUT_FILE, "w") as f:
        for repo_name in tqdm(sorted(all_repos), desc="Scraping repos"):
            try:
                pairs = scrape_repo(repo_name)
                for pair in pairs:
                    f.write(json.dumps(pair) + "\n")
                    all_pairs.append(pair)
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to scrape {repo_name}: {e}")
                continue

    # Summary
    flow_count = sum(1 for p in all_pairs if p["metadata"]["type"] == "flow")
    dw_count = sum(1 for p in all_pairs if p["metadata"]["type"] == "dataweave")

    logger.info(f"\n{'='*50}")
    logger.info(f"SCRAPING COMPLETE")
    logger.info(f"{'='*50}")
    logger.info(f"Total pairs: {len(all_pairs)}")
    logger.info(f"  Flows: {flow_count}")
    logger.info(f"  DataWeave: {dw_count}")
    logger.info(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
