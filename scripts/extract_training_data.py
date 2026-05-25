"""
MINT — Extract training data from local MuleSoft projects.

Reads your 132 MuleSoft projects and creates instruction-output pairs:
  - Input: description of what the flow does (from docs or flow name)
  - Output: the actual Mule XML code

Usage:
    python scripts/extract_training_data.py

Output:
    data/training.jsonl — ready for fine-tuning
"""

import json
import os
import re
from pathlib import Path

PROJECTS_DIR = Path("/Users/Raghavender/code-base-repo/mulesoft_projects")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"


def extract_flow_description(xml_content: str, file_path: str) -> str:
    """Extract a description of what the flow does from its content."""
    descriptions = []

    # Get flow names
    flow_names = re.findall(r'<flow\s+name="([^"]+)"', xml_content)
    if flow_names:
        descriptions.append(f"Flows: {', '.join(flow_names)}")

    # Get connectors used
    connectors = set()
    connector_patterns = [
        (r'<http:listener', 'HTTP Listener'),
        (r'<http:request', 'HTTP Request'),
        (r'<salesforce:', 'Salesforce'),
        (r'<db:', 'Database'),
        (r'<file:', 'File'),
        (r'<ftp:', 'FTP'),
        (r'<sftp:', 'SFTP'),
        (r'<jms:', 'JMS'),
        (r'<vm:', 'VM'),
        (r'<email:', 'Email'),
        (r'<s3:', 'Amazon S3'),
        (r'<sqs:', 'Amazon SQS'),
        (r'<sns:', 'Amazon SNS'),
        (r'<kafka:', 'Kafka'),
        (r'<batch:job', 'Batch Processing'),
        (r'<ee:transform', 'DataWeave Transform'),
        (r'<scatter-gather', 'Scatter-Gather'),
        (r'<try', 'Error Handling (Try)'),
        (r'<until-successful', 'Retry (Until Successful)'),
        (r'<foreach', 'For Each Loop'),
        (r'<choice', 'Choice Router'),
        (r'<logger', 'Logger'),
        (r'<set-variable', 'Set Variable'),
        (r'<set-payload', 'Set Payload'),
        (r'<object-store:', 'Object Store'),
    ]
    for pattern, name in connector_patterns:
        if re.search(pattern, xml_content):
            connectors.add(name)

    if connectors:
        descriptions.append(f"Components: {', '.join(sorted(connectors))}")

    # Get API path if HTTP listener
    paths = re.findall(r'path="([^"]+)"', xml_content)
    if paths:
        api_paths = [p for p in paths if p.startswith('/')]
        if api_paths:
            descriptions.append(f"API paths: {', '.join(api_paths[:3])}")

    return ". ".join(descriptions)


def read_functional_doc(project_dir: Path) -> str:
    """Read the functional document if it exists."""
    for name in ["Functional_Document.md", "functional_document.md", "README.md"]:
        doc_path = project_dir / name
        if doc_path.exists():
            content = doc_path.read_text(encoding="utf-8", errors="ignore")
            # Take first 500 chars as summary
            # Remove markdown headers and clean up
            lines = content.split("\n")
            summary_lines = []
            for line in lines[:30]:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("|"):
                    summary_lines.append(line)
                if len(" ".join(summary_lines)) > 400:
                    break
            return " ".join(summary_lines)[:500]
    return ""


def create_instruction_from_flow(xml_content: str, file_name: str, project_name: str, func_doc: str) -> dict:
    """Create an instruction-output training pair from a flow file."""

    # Build instruction
    flow_desc = extract_flow_description(xml_content, file_name)
    project_clean = project_name.replace("enterprise-mule-", "").replace("-", " ")

    if func_doc:
        instruction = f"Create a MuleSoft 4 flow for: {project_clean}. {func_doc[:200]}"
    elif flow_desc:
        instruction = f"Create a MuleSoft 4 flow with the following components: {flow_desc}"
    else:
        instruction = f"Create a MuleSoft 4 flow named '{file_name}' for the {project_clean} project."

    return {
        "instruction": instruction.strip(),
        "output": xml_content.strip(),
        "metadata": {
            "project": project_name,
            "file": file_name,
            "type": "flow",
        }
    }


def create_instruction_from_dwl(dwl_content: str, file_name: str, project_name: str) -> dict:
    """Create an instruction-output pair from a DataWeave file."""

    # Try to infer what the transform does from the file name
    name_clean = file_name.replace(".dwl", "").replace("-", " ").replace("_", " ")

    instruction = f"Write a DataWeave transformation for: {name_clean} (project: {project_name.replace('enterprise-mule-', '')})"

    return {
        "instruction": instruction.strip(),
        "output": dwl_content.strip(),
        "metadata": {
            "project": project_name,
            "file": file_name,
            "type": "dataweave",
        }
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("MINT — Extracting training data from local MuleSoft projects")
    print("=" * 60)
    print(f"Source: {PROJECTS_DIR}")

    training_data = []
    stats = {"projects": 0, "flows": 0, "dataweave": 0, "with_docs": 0}

    projects = sorted([d for d in PROJECTS_DIR.iterdir() if d.is_dir()])
    print(f"Found {len(projects)} projects\n")

    for project_dir in projects:
        project_name = project_dir.name
        stats["projects"] += 1

        # Read functional doc
        func_doc = read_functional_doc(project_dir)
        if func_doc:
            stats["with_docs"] += 1

        # Find all XML flow files
        xml_files = list(project_dir.rglob("src/main/mule/*.xml"))
        for xml_file in xml_files:
            try:
                content = xml_file.read_text(encoding="utf-8", errors="ignore")
                if len(content) < 50 or len(content) > 50000:  # Skip tiny/huge files
                    continue
                if "<mule" not in content and "<flow" not in content:
                    continue

                pair = create_instruction_from_flow(content, xml_file.name, project_name, func_doc)
                training_data.append(pair)
                stats["flows"] += 1
            except Exception as e:
                pass

        # Find all DataWeave files
        dwl_files = list(project_dir.rglob("*.dwl"))
        for dwl_file in dwl_files:
            try:
                content = dwl_file.read_text(encoding="utf-8", errors="ignore")
                if len(content) < 20 or len(content) > 10000:
                    continue

                pair = create_instruction_from_dwl(content, dwl_file.name, project_name)
                training_data.append(pair)
                stats["dataweave"] += 1
            except Exception as e:
                pass

    # Save training data
    output_path = OUTPUT_DIR / "training.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Also save a formatted version for inspection
    sample_path = OUTPUT_DIR / "training_sample.json"
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(training_data[:5], f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"  Projects scanned:    {stats['projects']}")
    print(f"  Projects with docs:  {stats['with_docs']}")
    print(f"  Flow pairs:          {stats['flows']}")
    print(f"  DataWeave pairs:     {stats['dataweave']}")
    print(f"  Total training pairs: {len(training_data)}")
    print(f"\n  Output: {output_path}")
    print(f"  Sample: {sample_path}")
    print(f"  Size:   {output_path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
