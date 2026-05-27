"""
MINT — Synthetic Data Generator using OpenAI GPT-4o-mini
==========================================================
Generates 10,000+ MuleSoft training pairs.
Validates each pair. Retries with error feedback if invalid.

Usage:
    export OPENAI_API_KEY="sk-your-key"
    python scripts/generate_synthetic_data.py --pairs 12000
"""

import json
import os
import re
import time
import argparse
import hashlib
import random
from pathlib import Path
from xml.etree import ElementTree as ET

OUTPUT_FILE = Path("data/synthetic_pairs.jsonl")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

seen_hashes = set()

# ============================================================
# PROMPTS — What to ask GPT-4o-mini to generate
# ============================================================
FLOW_SCENARIOS = [
    "HTTP REST API with GET and POST endpoints, error handling, and JSON response",
    "Kafka consumer that transforms messages with DataWeave and inserts into Database",
    "Salesforce query flow with OAuth2, error handling, and CSV export",
    "SAP IDoc receiver with acknowledgment and error logging",
    "SFTP file listener that reads CSV, transforms to JSON, and posts to REST API",
    "Batch job that reads from Database, processes in parallel, and upserts to Salesforce",
    "Scatter-gather with 3 parallel HTTP requests merged with DataWeave",
    "JMS consumer with transaction management and dead letter queue",
    "Scheduler that polls Database every 5 minutes and publishes changes to Kafka",
    "API-led experience layer with APIkit router, validation, and backend system call",
    "HTTP proxy that adds OAuth2 token, retries on failure, and logs with json-logger",
    "File-based integration: read XML from SFTP, transform to JSON, write to S3",
    "Event-driven: Salesforce Platform Events listener with Database sync",
    "Anypoint MQ consumer with acknowledgment and error handling",
    "VM queue publish-consume pattern for async processing",
    "MongoDB CRUD operations with HTTP API endpoints",
    "Redis cache lookup before calling expensive backend API",
    "Workday employee sync to Salesforce with field mapping",
    "ServiceNow incident creation from HTTP webhook",
    "Azure Service Bus consumer with blob storage write",
    "Google Pub/Sub listener with BigQuery insert",
    "Circuit breaker pattern with until-successful and fallback",
    "Content-based routing with choice router and 4 branches",
    "Idempotent message filter with object store",
    "OAuth2 client credentials flow with token caching",
    "TLS mutual authentication with client certificate",
    "API autodiscovery with rate limiting policies",
    "Watermark-based polling for incremental data sync",
    "Correlation ID propagation across multiple flows",
    "Global error handler with custom error types and HTTP status mapping",
]

DATAWEAVE_SCENARIOS = [
    "Flatten nested JSON array of orders with line items",
    "Group employees by department and calculate average salary",
    "Transform XML with namespaces to flat JSON",
    "CSV to JSON with date parsing and null handling",
    "Merge two payloads by matching ID field",
    "Filter array, remove nulls, and sort by date descending",
    "Map object keys from camelCase to snake_case",
    "Recursive flatten of deeply nested structure",
    "Coalesce multiple optional fields with defaults",
    "Pivot table transformation (rows to columns)",
    "Split large payload into batches of 200 records",
    "Calculate running total and percentage of grand total",
    "Parse multipart form data and extract file content",
    "Transform SOAP XML response to REST JSON format",
    "Dynamic field mapping based on configuration variable",
    "Date arithmetic: add business days excluding weekends",
    "Deduplicate array by composite key (firstName + lastName)",
    "Tree structure to flat list with parent references",
    "Conditional field inclusion based on payload type",
    "String template interpolation for email body generation",
]

SYSTEM_PROMPT = """You are an expert MuleSoft 4 developer. Generate training data pairs for a MuleSoft AI assistant.

RULES:
1. Generate ONLY valid Mule 4 XML (never Mule 3)
2. ALWAYS include ALL xmlns: namespace declarations for every prefix used
3. ALWAYS close all XML tags (end with </mule>)
4. Use real connector operations (http:listener, salesforce:query, kafka:publish, db:select, etc.)
5. Include doc:name and doc:id attributes
6. Never use: <component>, <inbound-endpoint>, <outbound-endpoint>, MEL expressions, session-variable
7. For DataWeave: always start with %dw 2.0, include output declaration, use --- separator

Return a JSON object with:
- "instruction": natural language request (what a developer would ask)
- "output": complete valid Mule 4 XML or DataWeave code"""


# ============================================================
# VALIDATION
# ============================================================
def validate_flow(output):
    """Validate a Mule 4 flow. Returns (valid, error_message)."""
    if "<mule" not in output:
        return False, "Missing <mule> root"
    if "</mule>" not in output:
        return False, "Truncated: missing </mule>"
    if "mulesoft.org/schema/mule" not in output:
        return False, "Missing mulesoft namespace"

    # Check Mule 3 garbage
    mule3 = ["<component", "<inbound-endpoint", "<outbound-endpoint",
             "<catch-exception-strategy", "<expression-transformer", "<poll>"]
    for m3 in mule3:
        if m3 in output:
            return False, f"Contains Mule 3 syntax: {m3}"

    # Check undeclared prefixes
    prefixes_used = set(re.findall(r'<(\w+):', output))
    prefixes_declared = set(re.findall(r'xmlns:(\w+)=', output))
    undeclared = prefixes_used - prefixes_declared - {"xml", "xsi"}
    if undeclared:
        return False, f"Undeclared prefixes: {', '.join(undeclared)}"

    # Try XML parse
    xml_match = re.search(r'(<\?xml.*?\?>.*?</mule>|<mule.*?</mule>)', output, re.DOTALL)
    if xml_match:
        try:
            ET.fromstring(xml_match.group(0))
            return True, ""
        except ET.ParseError as e:
            return False, f"XML parse error: {str(e)[:80]}"

    return True, ""  # Passes structural checks even if not perfectly parseable


def validate_dataweave(output):
    """Validate DataWeave output."""
    if "%dw" not in output:
        return False, "Missing %dw header"
    if "output " not in output:
        return False, "Missing output declaration"
    if "---" not in output:
        return False, "Missing --- separator"
    if len(output.strip()) < 50:
        return False, "Too short"
    return True, ""


def validate_pair(pair):
    """Validate a generated pair."""
    instruction = pair.get("instruction", "")
    output = pair.get("output", "")

    if not instruction or len(instruction) < 20:
        return False, "Instruction too short"
    if not output or len(output) < 100:
        return False, "Output too short"
    if len(output) > 50000:
        return False, "Output too long"

    # Dedup
    h = hashlib.md5(output[:500].encode()).hexdigest()
    if h in seen_hashes:
        return False, "Duplicate"
    seen_hashes.add(h)

    # Type detection
    if "<mule" in output or "<flow" in output:
        return validate_flow(output)
    elif "%dw" in output:
        return validate_dataweave(output)
    else:
        return False, "Neither flow nor DataWeave"


# ============================================================
# GENERATION WITH RETRY
# ============================================================
def call_openai(prompt, retry_feedback=None):
    """Call OpenAI API."""
    from openai import OpenAI
    client = OpenAI()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if retry_feedback:
        messages.append({"role": "user", "content": prompt})
        messages.append({"role": "assistant", "content": retry_feedback["bad_output"]})
        messages.append({"role": "user", "content": f"That output has an error: {retry_feedback['error']}. Fix it and regenerate. Return valid JSON with instruction and output fields."})
    else:
        messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        return None


def generate_one_pair(scenario, pair_type="flow"):
    """Generate one pair with validation and retry."""
    if pair_type == "flow":
        prompt = f"Generate a MuleSoft 4 training pair for this scenario: {scenario}. Return JSON with 'instruction' and 'output' (complete Mule 4 XML flow)."
    else:
        prompt = f"Generate a DataWeave 2.0 training pair for this scenario: {scenario}. Return JSON with 'instruction' and 'output' (complete DataWeave script)."

    # Attempt 1
    pair = call_openai(prompt)
    if not pair:
        return None

    valid, error = validate_pair(pair)
    if valid:
        pair["metadata"] = {"type": pair_type, "source": "synthetic_gpt4o_mini"}
        return pair

    # Attempt 2 — retry with error feedback
    pair2 = call_openai(prompt, retry_feedback={"bad_output": json.dumps(pair), "error": error})
    if not pair2:
        return None

    valid2, error2 = validate_pair(pair2)
    if valid2:
        pair2["metadata"] = {"type": pair_type, "source": "synthetic_gpt4o_mini_retry"}
        return pair2

    # Failed both attempts
    return None


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=12000)
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY environment variable")
        print("  export OPENAI_API_KEY='sk-your-key'")
        return

    target = args.pairs
    # 70% flows, 30% DataWeave
    flow_target = int(target * 0.7)
    dw_target = target - flow_target

    print(f"{'='*50}")
    print(f"  MINT Synthetic Data Generator")
    print(f"{'='*50}")
    print(f"  Target: {target} pairs ({flow_target} flows + {dw_target} DataWeave)")
    print(f"  Model: gpt-4o-mini")
    print(f"  Validation: XML parse + namespace + Mule3 check")
    print(f"  Retry: up to 2 attempts per pair")
    print(f"  Output: {OUTPUT_FILE}")
    print()

    generated = 0
    failed = 0
    f = open(OUTPUT_FILE, "w")

    # Generate flows
    print("Generating flows...")
    flow_count = 0
    round_num = 0
    while flow_count < flow_target:
        round_num += 1
        random.shuffle(FLOW_SCENARIOS)
        for scenario in FLOW_SCENARIOS:
            if flow_count >= flow_target:
                break

            # Add variation to avoid repetition
            variations = [
                scenario,
                f"{scenario} with comprehensive error handling",
                f"{scenario} using secure properties and TLS",
                f"{scenario} with json-logger logging at each step",
                f"{scenario} with retry logic and circuit breaker",
                f"Enterprise {scenario} following API-led connectivity pattern",
            ]
            prompt_scenario = variations[flow_count % len(variations)]

            pair = generate_one_pair(prompt_scenario, "flow")
            if pair:
                f.write(json.dumps(pair) + "\n")
                flow_count += 1
                generated += 1
            else:
                failed += 1

            if generated % 50 == 0:
                print(f"  Progress: {generated}/{target} generated, {failed} failed")

            time.sleep(0.5)  # Rate limit

    # Generate DataWeave
    print("\nGenerating DataWeave...")
    dw_count = 0
    while dw_count < dw_target:
        random.shuffle(DATAWEAVE_SCENARIOS)
        for scenario in DATAWEAVE_SCENARIOS:
            if dw_count >= dw_target:
                break

            variations = [
                scenario,
                f"{scenario} with error handling using try/orElse",
                f"{scenario} using custom functions",
                f"{scenario} with type coercion and null safety",
            ]
            prompt_scenario = variations[dw_count % len(variations)]

            pair = generate_one_pair(prompt_scenario, "dataweave")
            if pair:
                f.write(json.dumps(pair) + "\n")
                dw_count += 1
                generated += 1
            else:
                failed += 1

            if generated % 50 == 0:
                print(f"  Progress: {generated}/{target} generated, {failed} failed")

            time.sleep(0.5)

    f.close()

    print(f"\n{'='*50}")
    print(f"  GENERATION COMPLETE")
    print(f"{'='*50}")
    print(f"  Generated: {generated} valid pairs")
    print(f"  Failed/rejected: {failed}")
    print(f"  Success rate: {generated/(generated+failed)*100:.1f}%")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"\n  Next: merge with existing data and retrain:")
    print(f"    cat data/synthetic_pairs.jsonl >> data/training_merged.jsonl")
    print(f"    python scripts/resume_training.py")


if __name__ == "__main__":
    main()
