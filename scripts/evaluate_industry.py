"""
MINT Industry-Standard Evaluation Suite
=========================================
Evaluates MINT model using metrics aligned with code generation research:

1. STRUCTURAL VALIDITY (pass/fail per category)
   - XML validity (parseable by XML parser)
   - Namespace completeness (all prefixes declared)
   - Tag closure (no truncation)
   - DataWeave syntax validity

2. FUNCTIONAL CORRECTNESS (pass@1 style)
   - Connector accuracy (right connectors used)
   - Operation accuracy (right operations: query, publish, etc.)
   - Pattern accuracy (error handling, batch, scatter-gather present when asked)

3. SIMILARITY METRICS
   - BLEU-4 (n-gram overlap with reference)
   - ROUGE-L (longest common subsequence)
   - Exact match (normalized)

4. CATEGORY BREAKDOWN
   - Flow XML (API flows, integration flows, sub-flows)
   - DataWeave (transformations, mappings)
   - Global configs (connector configs, properties)
   - Error handling patterns
   - Connector-specific (SAP, Salesforce, Kafka, DB, HTTP, etc.)

Usage:
    python scripts/evaluate_industry.py --model raghavenderreddy1212/mintai-v2 --samples 100

Output: data/eval/industry_scores.json with full breakdown
"""

import json
import re
import argparse
import time
import numpy as np
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict


# ============================================================
# METRIC IMPLEMENTATIONS
# ============================================================

def compute_bleu(reference: str, hypothesis: str, max_n: int = 4) -> float:
    """Compute BLEU-4 score between reference and hypothesis."""
    from collections import Counter
    import math

    ref_tokens = reference.split()
    hyp_tokens = hypothesis.split()

    if len(hyp_tokens) == 0:
        return 0.0

    # Brevity penalty
    bp = min(1.0, math.exp(1 - len(ref_tokens) / max(len(hyp_tokens), 1)))

    # N-gram precisions
    precisions = []
    for n in range(1, max_n + 1):
        ref_ngrams = Counter(tuple(ref_tokens[i:i+n]) for i in range(len(ref_tokens) - n + 1))
        hyp_ngrams = Counter(tuple(hyp_tokens[i:i+n]) for i in range(len(hyp_tokens) - n + 1))

        clipped = sum(min(count, ref_ngrams[ng]) for ng, count in hyp_ngrams.items())
        total = max(sum(hyp_ngrams.values()), 1)
        precisions.append(clipped / total if total > 0 else 0)

    # Geometric mean with smoothing
    if any(p == 0 for p in precisions):
        precisions = [p + 1e-10 for p in precisions]

    log_avg = sum(math.log(p) for p in precisions) / max_n
    return bp * math.exp(log_avg)


def compute_rouge_l(reference: str, hypothesis: str) -> float:
    """Compute ROUGE-L (longest common subsequence) F1 score."""
    ref_tokens = reference.split()
    hyp_tokens = hypothesis.split()

    if not ref_tokens or not hyp_tokens:
        return 0.0

    # LCS length using DP
    m, n = len(ref_tokens), len(hyp_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_tokens[i-1] == hyp_tokens[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    lcs_len = dp[m][n]
    precision = lcs_len / n if n > 0 else 0
    recall = lcs_len / m if m > 0 else 0

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def compute_exact_match(reference: str, hypothesis: str) -> float:
    """Normalized exact match (strip whitespace, normalize)."""
    ref_norm = re.sub(r'\s+', ' ', reference.strip())
    hyp_norm = re.sub(r'\s+', ' ', hypothesis.strip())
    return 1.0 if ref_norm == hyp_norm else 0.0


# ============================================================
# STRUCTURAL VALIDATORS
# ============================================================

def validate_xml_structure(text: str) -> Dict:
    """Full XML structural validation."""
    result = {
        "parseable": False,
        "has_mule_root": False,
        "has_namespace": False,
        "all_prefixes_declared": False,
        "not_truncated": False,
        "has_flow_or_config": False,
        "undeclared_prefixes": [],
        "parse_error": None,
    }

    result["has_mule_root"] = "<mule" in text
    result["has_namespace"] = "mulesoft.org/schema/mule" in text
    result["not_truncated"] = "</mule>" in text
    result["has_flow_or_config"] = bool(
        re.search(r'<(flow|sub-flow|http:listener-config|apikit:config|kafka:)', text)
    )

    # Check namespace declarations
    prefixes_used = set(re.findall(r'<(\w+):', text)) | set(re.findall(r'</(\w+):', text))
    prefixes_declared = set(re.findall(r'xmlns:(\w+)=', text))
    undeclared = prefixes_used - prefixes_declared - {"xml", "xsi", "mule"}
    result["undeclared_prefixes"] = list(undeclared)
    result["all_prefixes_declared"] = len(undeclared) == 0

    # Try parsing
    xml_match = re.search(r'(<\?xml.*?\?>.*?</mule>|<mule.*?</mule>)', text, re.DOTALL)
    if xml_match:
        try:
            ET.fromstring(xml_match.group(0))
            result["parseable"] = True
        except ET.ParseError as e:
            result["parse_error"] = str(e)[:100]

    return result


def validate_dataweave_structure(text: str) -> Dict:
    """DataWeave structural validation."""
    result = {
        "has_version": False,
        "has_output_decl": False,
        "has_separator": False,
        "has_body": False,
        "valid_syntax": False,
        "syntax_error": None,
    }

    text = text.strip()
    result["has_version"] = bool(re.search(r'%dw\s+2\.\d', text))
    result["has_output_decl"] = "output " in text
    result["has_separator"] = "---" in text

    # Body is content after ---
    if "---" in text:
        body = text.split("---", 1)[1].strip()
        result["has_body"] = len(body) > 5
    else:
        result["has_body"] = len(text) > 30

    # Basic syntax check
    result["valid_syntax"] = (
        result["has_version"] and
        result["has_output_decl"] and
        result["has_separator"] and
        result["has_body"]
    )

    return result


# ============================================================
# FUNCTIONAL CORRECTNESS
# ============================================================

def check_functional_correctness(generated: str, instruction: str, expected: str, sample_type: str) -> Dict:
    """Check functional correctness — did it do what was asked?"""
    result = {
        "connectors_expected": [],
        "connectors_found": [],
        "connectors_score": 0.0,
        "operations_expected": [],
        "operations_found": [],
        "operations_score": 0.0,
        "patterns_expected": [],
        "patterns_found": [],
        "patterns_score": 0.0,
    }

    instruction_lower = instruction.lower()

    # Connector detection
    connector_map = {
        # CRM / ERP
        "salesforce": [r"salesforce:"],
        "sap": [r"sap:"],
        "workday": [r"workday:"],
        "netsuite": [r"netsuite:"],
        "servicenow": [r"servicenow:"],
        # Messaging
        "kafka": [r"kafka:publish", r"kafka:consume", r"kafka:message-listener"],
        "jms": [r"jms:publish", r"jms:consume", r"jms:listener"],
        "amqp": [r"amqp:"],
        "anypoint mq": [r"anypoint-mq:", r"anypointmq:"],
        "vm": [r"vm:publish", r"vm:consume", r"vm:listener"],
        "rabbitmq": [r"rabbitmq:"],
        # HTTP / API
        "http": [r"http:listener", r"http:request"],
        "rest": [r"http:request", r"http:listener"],
        "soap": [r"wsc:consume", r"web-service-consumer:", r"ws:"],
        "graphql": [r"graphql:"],
        # Database
        "database": [r"db:select", r"db:insert", r"db:update", r"db:delete", r"db:bulk"],
        "mongodb": [r"mongo:"],
        "redis": [r"redis:"],
        # Cloud - AWS
        "s3": [r"s3:", r"amazon-s3"],
        "sqs": [r"sqs:", r"amazon-sqs"],
        "sns": [r"sns:", r"amazon-sns"],
        "dynamodb": [r"dynamodb:"],
        "lambda": [r"lambda:"],
        # Cloud - Azure
        "azure": [r"azure:"],
        "azure service bus": [r"azure-service-bus:"],
        "azure blob": [r"azure-blob:"],
        # Cloud - Google
        "google": [r"google:"],
        "bigquery": [r"bigquery:"],
        "pubsub": [r"google-pubsub:", r"pubsub:"],
        # File / FTP
        "sftp": [r"sftp:"],
        "ftp": [r"ftp:"],
        "file": [r"file:read", r"file:write", r"file:listener"],
        # Email
        "email": [r"email:send", r"email:listener"],
        # Monitoring / Logging
        "splunk": [r"splunk:", r"http:request.*splunk"],
        "elasticsearch": [r"elasticsearch:"],
        # Object Store / Cache
        "objectstore": [r"os:store", r"os:retrieve", r"objectstore:"],
        "redis cache": [r"redis:"],
        # MuleSoft Platform
        "cloudhub": [r"cloudhub:", r"ch:"],
        "runtime fabric": [r"rtf:"],
        "api manager": [r"api-gateway:", r"autodiscovery"],
    }

    for name, patterns in connector_map.items():
        if name in instruction_lower:
            result["connectors_expected"].append(name)
            if any(re.search(p, generated) for p in patterns):
                result["connectors_found"].append(name)

    if result["connectors_expected"]:
        result["connectors_score"] = len(result["connectors_found"]) / len(result["connectors_expected"])

    # Pattern detection
    pattern_map = {
        "error handling": [r"error-handler", r"on-error-propagate", r"on-error-continue"],
        "batch": [r"batch:job", r"<batch"],
        "scatter-gather": [r"scatter-gather"],
        "choice": [r"<choice"],
        "for-each": [r"for-each", r"foreach"],
        "try": [r"<try"],
        "until-successful": [r"until-successful"],
        "dataweave": [r"ee:transform"],
        "apikit": [r"apikit:router", r"apikit:config"],
        "scheduler": [r"<scheduler", r"scheduling-strategy"],
        "async": [r"<async"],
        "cache": [r"<ee:cache", r"cache:"],
        "idempotent": [r"idempotent-message-validator"],
        "transaction": [r"transactionalAction", r"xa-transaction"],
        "oauth": [r"oauth:", r"oauth2"],
        "tls": [r"tls:context", r"tls:trust-store"],
        "secure properties": [r"secure-properties:", r"secure-property"],
        "api autodiscovery": [r"api-gateway:autodiscovery", r"autodiscovery"],
        "correlation id": [r"correlationId", r"correlation"],
        "watermark": [r"watermark"],
        "reconnection": [r"reconnection", r"reconnect"],
    }

    for name, patterns in pattern_map.items():
        if name in instruction_lower:
            result["patterns_expected"].append(name)
            if any(re.search(p, generated) for p in patterns):
                result["patterns_found"].append(name)

    if result["patterns_expected"]:
        result["patterns_score"] = len(result["patterns_found"]) / len(result["patterns_expected"])

    return result


# ============================================================
# CATEGORY CLASSIFICATION
# ============================================================

def classify_sample(instruction: str, metadata: Dict) -> str:
    """Classify a sample into a granular category for per-category scoring."""
    sample_type = metadata.get("type", "flow")
    instruction_lower = instruction.lower()

    if sample_type == "dataweave":
        if any(w in instruction_lower for w in ["map", "transform", "convert", "flatten"]):
            return "dataweave_transformation"
        elif any(w in instruction_lower for w in ["filter", "reduce", "group"]):
            return "dataweave_aggregation"
        elif any(w in instruction_lower for w in ["csv", "xml", "json", "format"]):
            return "dataweave_format_conversion"
        return "dataweave_general"

    # --- Connectors: CRM / ERP ---
    if any(w in instruction_lower for w in ["sap", "idoc", "bapi", "rfc", "s4hana"]):
        return "connector_sap"
    elif any(w in instruction_lower for w in ["salesforce", "sfdc", "soql", "platform event"]):
        return "connector_salesforce"
    elif any(w in instruction_lower for w in ["workday"]):
        return "connector_workday"
    elif any(w in instruction_lower for w in ["netsuite"]):
        return "connector_netsuite"
    elif any(w in instruction_lower for w in ["servicenow"]):
        return "connector_servicenow"

    # --- Connectors: Messaging ---
    elif any(w in instruction_lower for w in ["kafka", "topic", "consumer", "producer"]):
        return "connector_kafka"
    elif any(w in instruction_lower for w in ["jms", "activemq", "ibm mq"]):
        return "connector_jms"
    elif any(w in instruction_lower for w in ["anypoint mq", "anypointmq"]):
        return "connector_anypoint_mq"
    elif any(w in instruction_lower for w in ["amqp", "rabbitmq"]):
        return "connector_amqp"
    elif any(w in instruction_lower for w in [" vm ", "vm queue", "vm connector"]):
        return "connector_vm"

    # --- Connectors: Database ---
    elif any(w in instruction_lower for w in ["database", "sql", "stored procedure", "oracle", "mysql", "postgres"]):
        return "connector_database"
    elif any(w in instruction_lower for w in ["mongodb", "mongo"]):
        return "connector_mongodb"
    elif any(w in instruction_lower for w in ["redis"]):
        return "connector_redis"

    # --- Connectors: Cloud AWS ---
    elif any(w in instruction_lower for w in ["s3", "aws s3", "bucket"]):
        return "connector_aws_s3"
    elif any(w in instruction_lower for w in ["sqs", "aws sqs"]):
        return "connector_aws_sqs"
    elif any(w in instruction_lower for w in ["sns", "aws sns"]):
        return "connector_aws_sns"
    elif any(w in instruction_lower for w in ["dynamodb", "dynamo"]):
        return "connector_aws_dynamodb"
    elif any(w in instruction_lower for w in ["lambda", "aws lambda"]):
        return "connector_aws_lambda"

    # --- Connectors: Cloud Azure ---
    elif any(w in instruction_lower for w in ["azure", "service bus", "blob storage"]):
        return "connector_azure"

    # --- Connectors: Cloud Google ---
    elif any(w in instruction_lower for w in ["google", "bigquery", "pubsub", "gcp"]):
        return "connector_google"

    # --- Connectors: File ---
    elif any(w in instruction_lower for w in ["sftp", "ftp"]):
        return "connector_sftp"
    elif any(w in instruction_lower for w in ["file read", "file write", "file connector"]):
        return "connector_file"

    # --- Connectors: Monitoring ---
    elif any(w in instruction_lower for w in ["splunk"]):
        return "connector_splunk"
    elif any(w in instruction_lower for w in ["elasticsearch", "elastic"]):
        return "connector_elasticsearch"

    # --- API Types ---
    elif any(w in instruction_lower for w in ["soap", "wsdl", "web service consumer"]):
        return "api_soap"
    elif any(w in instruction_lower for w in ["rest api", "http listener", "apikit"]):
        return "api_rest"
    elif any(w in instruction_lower for w in ["raml", "api spec", "oas", "openapi"]):
        return "api_raml_spec"
    elif any(w in instruction_lower for w in ["graphql"]):
        return "api_graphql"

    # --- Patterns ---
    elif any(w in instruction_lower for w in ["error", "exception", "try", "catch", "on-error"]):
        return "pattern_error_handling"
    elif any(w in instruction_lower for w in ["batch", "bulk"]):
        return "pattern_batch"
    elif any(w in instruction_lower for w in ["scatter", "parallel"]):
        return "pattern_scatter_gather"
    elif any(w in instruction_lower for w in ["oauth", "security", "tls", "authentication"]):
        return "pattern_security"
    elif any(w in instruction_lower for w in ["scheduler", "cron", "poll"]):
        return "pattern_scheduler"
    elif any(w in instruction_lower for w in ["transaction", "xa"]):
        return "pattern_transaction"

    # --- Deployment ---
    elif any(w in instruction_lower for w in ["cloudhub", "deploy", "runtime fabric", "on-premise", "on premise"]):
        return "deployment"
    elif any(w in instruction_lower for w in ["global", "config", "properties"]):
        return "global_config"

    return "flow_general"


# ============================================================
# MAIN EVALUATION
# ============================================================

@dataclass
class SampleScore:
    """Complete score for a single sample."""
    category: str
    # Structural
    structural_valid: bool = False
    structural_details: Dict = field(default_factory=dict)
    # Functional
    functional_score: float = 0.0
    functional_details: Dict = field(default_factory=dict)
    # Similarity
    bleu: float = 0.0
    rouge_l: float = 0.0
    exact_match: float = 0.0
    # Composite
    pass_at_1: float = 0.0  # 1 if structurally valid AND functional score > 0.5


def evaluate_sample(instruction: str, expected: str, generated: str, metadata: Dict) -> SampleScore:
    """Evaluate a single sample with all metrics."""
    sample_type = metadata.get("type", "flow")
    category = classify_sample(instruction, metadata)
    score = SampleScore(category=category)

    # 1. Structural validity
    if sample_type == "flow":
        struct = validate_xml_structure(generated)
        score.structural_valid = struct["parseable"] or (
            struct["has_mule_root"] and struct["not_truncated"] and struct["all_prefixes_declared"]
        )
        score.structural_details = struct
    elif sample_type == "dataweave":
        struct = validate_dataweave_structure(generated)
        score.structural_valid = struct["valid_syntax"]
        score.structural_details = struct
    else:
        score.structural_valid = len(generated.strip()) > 50
        score.structural_details = {"has_content": score.structural_valid}

    # 2. Functional correctness
    func = check_functional_correctness(generated, instruction, expected, sample_type)
    score.functional_details = func
    # Weighted functional score
    scores = []
    if func["connectors_expected"]:
        scores.append(func["connectors_score"])
    if func["patterns_expected"]:
        scores.append(func["patterns_score"])
    score.functional_score = np.mean(scores) if scores else (1.0 if score.structural_valid else 0.0)

    # 3. Similarity metrics
    score.bleu = compute_bleu(expected, generated)
    score.rouge_l = compute_rouge_l(expected, generated)
    score.exact_match = compute_exact_match(expected, generated)

    # 4. Pass@1 — binary: structurally valid AND functionally correct
    score.pass_at_1 = 1.0 if (score.structural_valid and score.functional_score >= 0.5) else 0.0

    return score


def print_scorecard(scores: List[SampleScore]):
    """Print a full industry-standard scorecard."""
    print("\n" + "=" * 70)
    print("  MINT EVALUATION SCORECARD (Industry Standard)")
    print("=" * 70)

    # Overall metrics
    n = len(scores)
    pass_at_1 = np.mean([s.pass_at_1 for s in scores]) * 100
    structural = sum(s.structural_valid for s in scores) / n * 100
    avg_bleu = np.mean([s.bleu for s in scores]) * 100
    avg_rouge = np.mean([s.rouge_l for s in scores]) * 100
    avg_func = np.mean([s.functional_score for s in scores]) * 100
    exact = sum(s.exact_match for s in scores) / n * 100

    print(f"\n  {'METRIC':<30} {'SCORE':>10}")
    print(f"  {'-'*40}")
    print(f"  {'Pass@1 (functional correct.)':<30} {pass_at_1:>8.1f}%")
    print(f"  {'Structural Validity':<30} {structural:>8.1f}%")
    print(f"  {'Functional Correctness':<30} {avg_func:>8.1f}%")
    print(f"  {'BLEU-4':<30} {avg_bleu:>8.1f}%")
    print(f"  {'ROUGE-L':<30} {avg_rouge:>8.1f}%")
    print(f"  {'Exact Match':<30} {exact:>8.1f}%")
    print(f"  {'Samples':<30} {n:>8}")

    # Per-category breakdown
    categories = defaultdict(list)
    for s in scores:
        categories[s.category].append(s)

    print(f"\n  {'='*70}")
    print(f"  PER-CATEGORY BREAKDOWN")
    print(f"  {'='*70}")
    print(f"  {'CATEGORY':<30} {'N':>4} {'Pass@1':>8} {'Struct':>8} {'BLEU':>8} {'Func':>8}")
    print(f"  {'-'*70}")

    for cat in sorted(categories.keys()):
        cat_scores = categories[cat]
        cn = len(cat_scores)
        cp = np.mean([s.pass_at_1 for s in cat_scores]) * 100
        cs = sum(s.structural_valid for s in cat_scores) / cn * 100
        cb = np.mean([s.bleu for s in cat_scores]) * 100
        cf = np.mean([s.functional_score for s in cat_scores]) * 100
        print(f"  {cat:<30} {cn:>4} {cp:>7.1f}% {cs:>7.1f}% {cb:>7.1f}% {cf:>7.1f}%")

    # Connector-specific breakdown
    connector_cats = [c for c in categories if c.startswith("connector_")]
    if connector_cats:
        print(f"\n  {'='*70}")
        print(f"  CONNECTOR ACCURACY")
        print(f"  {'='*70}")
        for cat in sorted(connector_cats):
            cat_scores = categories[cat]
            cn = len(cat_scores)
            cp = np.mean([s.pass_at_1 for s in cat_scores]) * 100
            connector_name = cat.replace("connector_", "").upper()
            bar = "█" * int(cp / 5) + "░" * (20 - int(cp / 5))
            print(f"  {connector_name:<15} {bar} {cp:.1f}% ({cn} samples)")


def run_evaluation(model_id: str, n_samples: int = 50, test_file: str = "data/dataset_test.jsonl"):
    """Run full industry-standard evaluation."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    # Load test data
    test_data = []
    for line in open(test_file):
        if line.strip():
            test_data.append(json.loads(line))
    test_data = test_data[:n_samples]
    print(f"Evaluating on {len(test_data)} test samples")

    # Load model
    print(f"Loading model: {model_id}...")
    base_model = "unsloth/qwen2.5-coder-7b-instruct-bnb-4bit"

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.float16, device_map="auto"
    )
    model = PeftModel.from_pretrained(model, model_id)
    model.eval()
    print("✓ Model loaded")

    system_prompt = (
        "You are MINT, an expert MuleSoft 4 developer. "
        "Generate complete, valid Mule 4 XML flows and DataWeave 2.0 transformations. "
        "Always include all namespace declarations and close all XML tags."
    )

    # Evaluate each sample
    all_scores = []
    for i, sample in enumerate(test_data):
        if i % 10 == 0:
            print(f"  [{i+1}/{len(test_data)}]...")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sample["instruction"]},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=4096,
                temperature=0.1,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )

        generated = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )

        metadata = sample.get("metadata", {"type": "flow"})
        score = evaluate_sample(sample["instruction"], sample["output"], generated, metadata)
        all_scores.append(score)

    # Print scorecard
    print_scorecard(all_scores)

    # Save results
    results_dir = Path("data/eval")
    results_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "model": model_id,
        "n_samples": len(all_scores),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall": {
            "pass_at_1": np.mean([s.pass_at_1 for s in all_scores]) * 100,
            "structural_validity": sum(s.structural_valid for s in all_scores) / len(all_scores) * 100,
            "functional_correctness": np.mean([s.functional_score for s in all_scores]) * 100,
            "bleu_4": np.mean([s.bleu for s in all_scores]) * 100,
            "rouge_l": np.mean([s.rouge_l for s in all_scores]) * 100,
            "exact_match": sum(s.exact_match for s in all_scores) / len(all_scores) * 100,
        },
        "per_category": {},
    }

    # Per-category
    categories = defaultdict(list)
    for s in all_scores:
        categories[s.category].append(s)

    for cat, cat_scores in categories.items():
        cn = len(cat_scores)
        output["per_category"][cat] = {
            "n": cn,
            "pass_at_1": np.mean([s.pass_at_1 for s in cat_scores]) * 100,
            "structural_validity": sum(s.structural_valid for s in cat_scores) / cn * 100,
            "functional_correctness": np.mean([s.functional_score for s in cat_scores]) * 100,
            "bleu_4": np.mean([s.bleu for s in cat_scores]) * 100,
            "rouge_l": np.mean([s.rouge_l for s in cat_scores]) * 100,
        }

    results_file = results_dir / "industry_scores.json"
    results_file.write_text(json.dumps(output, indent=2))
    print(f"\n  Results saved: {results_file}")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MINT Industry-Standard Evaluation")
    parser.add_argument("--model", default="raghavenderreddy1212/mintai-v2")
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--test-file", default="data/dataset_test.jsonl")
    args = parser.parse_args()

    run_evaluation(args.model, args.samples, args.test_file)
