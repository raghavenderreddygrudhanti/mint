"""
MINT Data Collection — Scrape MuleSoft code from GitHub.

Finds Mule 4 projects by searching for mule-artifact.json,
then extracts XML flows, DataWeave files, and RAML specs.

Usage:
    python scripts/scrape_github.py --token YOUR_GITHUB_TOKEN --max-repos 500

Output:
    data/raw/repos.json          — list of discovered repos
    data/raw/flows/*.xml         — extracted Mule flow files
    data/raw/dataweave/*.dwl     — extracted DataWeave files
    data/raw/metadata.jsonl      — file metadata (repo, path, connectors)
"""

import argparse
import json
import os
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
GITHUB_API = "https://api.github.com"


def search_repos(token: str, max_repos: int = 500) -> list[dict]:
    """Search GitHub for Mule 4 repositories."""
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    repos = []
    queries = [
        "mule-artifact.json in:path",
        "mulesoft language:XML",
        "topic:mulesoft",
        "topic:mule4",
        "anypoint mule language:XML",
    ]

    for query in queries:
        if len(repos) >= max_repos:
            break

        page = 1
        while page <= 10 and len(repos) < max_repos:
            print(f"  Searching: '{query}' page {page}...")
            resp = requests.get(
                f"{GITHUB_API}/search/repositories",
                headers=headers,
                params={"q": query, "per_page": 100, "page": page, "sort": "stars"},
            )

            if resp.status_code == 403:
                print("  Rate limited. Waiting 60s...")
                time.sleep(60)
                continue

            if resp.status_code != 200:
                print(f"  Error {resp.status_code}: {resp.text[:100]}")
                break

            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                repo_info = {
                    "full_name": item["full_name"],
                    "url": item["html_url"],
                    "stars": item["stargazers_count"],
                    "language": item.get("language"),
                    "description": item.get("description", ""),
                }
                if repo_info["full_name"] not in {r["full_name"] for r in repos}:
                    repos.append(repo_info)

            page += 1
            time.sleep(2)  # Rate limit courtesy

    print(f"  Found {len(repos)} unique repos")
    return repos[:max_repos]


def get_mule_files(repo_full_name: str, token: str) -> list[dict]:
    """Get all Mule-related files from a repo using the tree API."""
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    # Get default branch
    resp = requests.get(f"{GITHUB_API}/repos/{repo_full_name}", headers=headers)
    if resp.status_code != 200:
        return []
    default_branch = resp.json().get("default_branch", "main")

    # Get file tree
    resp = requests.get(
        f"{GITHUB_API}/repos/{repo_full_name}/git/trees/{default_branch}",
        headers=headers,
        params={"recursive": "1"},
    )
    if resp.status_code != 200:
        return []

    tree = resp.json().get("tree", [])
    mule_files = []

    for item in tree:
        if item["type"] != "blob":
            continue
        path = item["path"]
        if any([
            path.endswith(".xml") and "src/main/mule" in path,
            path.endswith(".dwl"),
            path.endswith(".raml"),
            path == "mule-artifact.json",
        ]):
            mule_files.append({
                "path": path,
                "sha": item["sha"],
                "size": item.get("size", 0),
                "type": "flow" if ".xml" in path else "dataweave" if ".dwl" in path else "raml",
            })

    return mule_files


def download_file(repo_full_name: str, file_path: str, token: str) -> str:
    """Download a single file's content from GitHub."""
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.raw"}
    resp = requests.get(
        f"{GITHUB_API}/repos/{repo_full_name}/contents/{file_path}",
        headers=headers,
    )
    if resp.status_code == 200:
        return resp.text
    return ""


def extract_connectors(xml_content: str) -> list[str]:
    """Extract connector names from Mule XML."""
    import re
    # Find namespace prefixes that indicate connectors
    connectors = set()
    patterns = [
        r'<(http|salesforce|db|file|ftp|sftp|jms|vm|email|s3|sqs|sns):',
        r'<(batch|ee|os|scripting|validation|json|xml|csv):',
        r'xmlns:(\w+)="http://www.mulesoft.org/schema/mule/(\w+)"',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, xml_content)
        for match in matches:
            if isinstance(match, tuple):
                connectors.add(match[0])
            else:
                connectors.add(match)
    return sorted(connectors)


def main():
    parser = argparse.ArgumentParser(description="Scrape MuleSoft code from GitHub")
    parser.add_argument("--token", required=True, help="GitHub personal access token")
    parser.add_argument("--max-repos", type=int, default=200, help="Max repos to scrape")
    parser.add_argument("--max-files", type=int, default=5000, help="Max files to download")
    args = parser.parse_args()

    # Create output dirs
    (DATA_DIR / "flows").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "dataweave").mkdir(parents=True, exist_ok=True)

    # Step 1: Find repos
    print("[1/3] Searching for MuleSoft repos...")
    repos = search_repos(args.token, args.max_repos)

    repos_path = DATA_DIR / "repos.json"
    with open(repos_path, "w") as f:
        json.dump(repos, f, indent=2)
    print(f"  Saved: {repos_path}")

    # Step 2: Get file lists
    print(f"\n[2/3] Scanning {len(repos)} repos for Mule files...")
    all_files = []
    for i, repo in enumerate(repos):
        if len(all_files) >= args.max_files:
            break
        if i % 10 == 0:
            print(f"  Scanning repo {i+1}/{len(repos)}: {repo['full_name']}")
        files = get_mule_files(repo["full_name"], args.token)
        for f in files:
            f["repo"] = repo["full_name"]
        all_files.extend(files)
        time.sleep(1)  # Rate limit

    print(f"  Found {len(all_files)} Mule files")

    # Step 3: Download files
    print(f"\n[3/3] Downloading files...")
    metadata = []
    downloaded = 0

    for i, file_info in enumerate(all_files[:args.max_files]):
        if i % 50 == 0:
            print(f"  Downloading {i+1}/{min(len(all_files), args.max_files)}...")

        content = download_file(file_info["repo"], file_info["path"], args.token)
        if not content:
            continue

        # Save file
        safe_name = f"{file_info['repo'].replace('/', '_')}_{Path(file_info['path']).name}"
        if file_info["type"] == "flow":
            out_path = DATA_DIR / "flows" / safe_name
        elif file_info["type"] == "dataweave":
            out_path = DATA_DIR / "dataweave" / safe_name
        else:
            continue

        out_path.write_text(content, encoding="utf-8")
        downloaded += 1

        # Extract metadata
        meta = {
            "repo": file_info["repo"],
            "path": file_info["path"],
            "type": file_info["type"],
            "local_file": str(out_path.name),
            "size": len(content),
        }
        if file_info["type"] == "flow":
            meta["connectors"] = extract_connectors(content)
        metadata.append(meta)

        time.sleep(0.5)  # Rate limit

    # Save metadata
    meta_path = DATA_DIR / "metadata.jsonl"
    with open(meta_path, "w") as f:
        for m in metadata:
            f.write(json.dumps(m) + "\n")

    print(f"\n✓ Done!")
    print(f"  Repos found: {len(repos)}")
    print(f"  Files downloaded: {downloaded}")
    print(f"  Flows: {sum(1 for m in metadata if m['type'] == 'flow')}")
    print(f"  DataWeave: {sum(1 for m in metadata if m['type'] == 'dataweave')}")
    print(f"  Metadata: {meta_path}")


if __name__ == "__main__":
    main()
