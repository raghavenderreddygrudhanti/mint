"""
MINT MuleSoft Parser — Extract structured metadata from Mule projects.

Parses XML flows, DataWeave, RAML, and config files into structured metadata
that powers the RAG and Graph RAG pipelines.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from xml.etree import ElementTree as ET


@dataclass
class FlowMetadata:
    """Structured metadata for a single Mule flow."""
    app_name: str
    flow_name: str
    flow_type: str  # "flow", "sub-flow", "error-handler"
    file_path: str
    connectors: list[str] = field(default_factory=list)
    systems: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)
    http_paths: list[str] = field(default_factory=list)
    error_handlers: bool = False
    has_dataweave: bool = False
    has_batch: bool = False
    has_scatter_gather: bool = False
    variables_set: list[str] = field(default_factory=list)
    flow_refs: list[str] = field(default_factory=list)  # calls to other flows
    description: str = ""


@dataclass
class AppMetadata:
    """Structured metadata for an entire Mule application."""
    name: str
    path: str
    flows: list[FlowMetadata] = field(default_factory=list)
    connectors_used: list[str] = field(default_factory=list)
    systems_integrated: list[str] = field(default_factory=list)
    dataweave_files: list[str] = field(default_factory=list)
    has_munit: bool = False
    has_error_handling: bool = False
    api_spec: Optional[str] = None  # RAML/OAS path
    description: str = ""


# Connector → System mapping
CONNECTOR_SYSTEM_MAP = {
    "salesforce": "Salesforce",
    "db": "Database",
    "http": "HTTP/REST",
    "https": "HTTP/REST",
    "kafka": "Kafka",
    "jms": "JMS/ActiveMQ",
    "vm": "VM Queue",
    "file": "File System",
    "ftp": "FTP",
    "sftp": "SFTP",
    "email": "Email/SMTP",
    "s3": "AWS S3",
    "sqs": "AWS SQS",
    "sns": "AWS SNS",
    "dynamodb": "AWS DynamoDB",
    "azure": "Azure",
    "workday": "Workday",
    "sap": "SAP",
    "servicenow": "ServiceNow",
    "netsuite": "NetSuite",
    "slack": "Slack",
    "twilio": "Twilio",
    "redis": "Redis",
    "mongodb": "MongoDB",
    "elasticsearch": "Elasticsearch",
    "anypoint-mq": "Anypoint MQ",
    "os": "Object Store",
    "oauth": "OAuth",
}


def parse_mule_xml(xml_path: Path, app_name: str) -> list[FlowMetadata]:
    """Parse a Mule XML file and extract flow metadata."""
    try:
        content = xml_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    flows = []

    # Extract flow names and types
    flow_patterns = [
        (r'<flow\s+name="([^"]+)"', "flow"),
        (r'<sub-flow\s+name="([^"]+)"', "sub-flow"),
    ]

    for pattern, flow_type in flow_patterns:
        for match in re.finditer(pattern, content):
            flow_name = match.group(1)

            # Find the flow's content (approximate — between this flow tag and next)
            start = match.start()
            end_tag = f"</{flow_type}>" if flow_type == "flow" else "</sub-flow>"
            end = content.find(end_tag, start)
            if end == -1:
                end = len(content)
            flow_content = content[start:end]

            # Extract connectors
            connectors = set()
            operations = []
            systems = set()

            connector_patterns = [
                (r'<(\w+):(\w+)', None),  # generic namespace:operation
            ]

            for ns_match in re.finditer(r'<(\w+):(\w+)', flow_content):
                ns = ns_match.group(1)
                op = ns_match.group(2)
                if ns in CONNECTOR_SYSTEM_MAP:
                    connectors.add(ns)
                    systems.add(CONNECTOR_SYSTEM_MAP[ns])
                    operations.append(f"{ns}:{op}")

            # HTTP paths
            http_paths = re.findall(r'path="(/[^"]*)"', flow_content)

            # Error handling
            has_error = bool(re.search(r'<error-handler|<on-error|<try', flow_content))

            # DataWeave
            has_dw = bool(re.search(r'<ee:transform|CDATA\[%dw', flow_content))

            # Batch
            has_batch = bool(re.search(r'<batch:', flow_content))

            # Scatter-gather
            has_sg = bool(re.search(r'<scatter-gather', flow_content))

            # Variables
            variables = re.findall(r'variableName="([^"]+)"', flow_content)

            # Flow references
            flow_refs = re.findall(r'<flow-ref\s+name="([^"]+)"', flow_content)

            flows.append(FlowMetadata(
                app_name=app_name,
                flow_name=flow_name,
                flow_type=flow_type,
                file_path=str(xml_path),
                connectors=sorted(connectors),
                systems=sorted(systems),
                operations=operations[:10],  # limit
                http_paths=http_paths,
                error_handlers=has_error,
                has_dataweave=has_dw,
                has_batch=has_batch,
                has_scatter_gather=has_sg,
                variables_set=variables[:10],
                flow_refs=flow_refs,
            ))

    return flows


def parse_app(app_dir: Path) -> AppMetadata:
    """Parse an entire MuleSoft application directory."""
    app_name = app_dir.name

    # Find all XML flow files
    xml_files = list(app_dir.rglob("src/main/mule/*.xml"))
    all_flows = []
    all_connectors = set()
    all_systems = set()

    for xml_file in xml_files:
        flows = parse_mule_xml(xml_file, app_name)
        all_flows.extend(flows)
        for f in flows:
            all_connectors.update(f.connectors)
            all_systems.update(f.systems)

    # DataWeave files
    dwl_files = [str(f.name) for f in app_dir.rglob("*.dwl")]

    # MUnit tests
    has_munit = any(app_dir.rglob("src/test/munit/*.xml"))

    # API spec
    api_spec = None
    for ext in ["*.raml", "*.yaml", "*.yml"]:
        specs = list(app_dir.rglob(f"src/main/resources/api/{ext}"))
        if specs:
            api_spec = str(specs[0].name)
            break

    # Description from docs
    description = ""
    for doc_name in ["Functional_Document.md", "README.md"]:
        doc_path = app_dir / doc_name
        if doc_path.exists():
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
            # First meaningful paragraph
            for line in text.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 50:
                    description = line[:300]
                    break
            break

    return AppMetadata(
        name=app_name,
        path=str(app_dir),
        flows=all_flows,
        connectors_used=sorted(all_connectors),
        systems_integrated=sorted(all_systems),
        dataweave_files=dwl_files[:20],
        has_munit=has_munit,
        has_error_handling=any(f.error_handlers for f in all_flows),
        api_spec=api_spec,
        description=description,
    )


def parse_all_projects(projects_dir: Path) -> list[AppMetadata]:
    """Parse all MuleSoft projects in a directory."""
    apps = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        app = parse_app(project_dir)
        if app.flows:  # Only include apps with actual flows
            apps.append(app)
    return apps


def save_metadata(apps: list[AppMetadata], output_path: Path):
    """Save parsed metadata to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(app) for app in apps]
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(data)


if __name__ == "__main__":
    PROJECTS_DIR = Path("/Users/Raghavender/code-base-repo/mulesoft_projects")
    OUTPUT = Path("/Users/Raghavender/lang-chain/mint/data/metadata.json")

    print("MINT Parser — Extracting MuleSoft metadata")
    print("=" * 60)

    apps = parse_all_projects(PROJECTS_DIR)

    total_flows = sum(len(a.flows) for a in apps)
    total_connectors = set()
    total_systems = set()
    for a in apps:
        total_connectors.update(a.connectors_used)
        total_systems.update(a.systems_integrated)

    print(f"  Apps parsed:      {len(apps)}")
    print(f"  Total flows:      {total_flows}")
    print(f"  Connectors used:  {sorted(total_connectors)}")
    print(f"  Systems:          {sorted(total_systems)}")

    n = save_metadata(apps, OUTPUT)
    print(f"\n  Saved: {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")
