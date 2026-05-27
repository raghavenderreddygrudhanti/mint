"""
MINT — Verify LoRA is Working
===============================
Compares base model output vs fine-tuned model output
to prove the LoRA adapter is influencing generation.

If both outputs are identical → LoRA is NOT loaded correctly.
If fine-tuned output has your training patterns → LoRA is working.

Usage:
    python scripts/verify_lora.py
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL = "unsloth/qwen2.5-coder-7b-instruct-bnb-4bit"
LORA_MODEL = "raghavenderreddy1212/mintai-v2"

# Test prompts that should show clear differences
TEST_PROMPTS = [
    "Create a MuleSoft 4 HTTP listener flow on port 8081 with error handling",
    "Write DataWeave to transform a list of accounts to CSV",
    "Create a Kafka consumer flow that publishes to Salesforce",
]

# Patterns that indicate your training data influenced the output
# (these are specific to your enterprise training data)
TRAINING_FINGERPRINTS = [
    "json-logger:",                    # Your training data uses json-logger
    "error-handler-plugin:",           # Custom error handler plugin
    "${api.name}/api/${api.version}",  # Enterprise URL pattern
    "JSON_Logger_Config",              # Specific config name from your data
    "Error_Handler_Plugin_Config",     # Specific config name
    "HTTPS_Listener_config",           # Specific listener config
    "doc:id=",                         # Anypoint Studio doc IDs
    "tracePoint=",                     # json-logger trace points
    "vars.httpStatus",                 # Enterprise variable pattern
    "vars.outboundHeaders",            # Enterprise header pattern
]


def generate(model, tokenizer, prompt: str, max_tokens: int = 1024) -> str:
    """Generate output from a model."""
    messages = [
        {"role": "system", "content": "You are MINT, an expert MuleSoft developer. Generate complete, valid Mule 4 XML flows and DataWeave transformations."},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=0.1,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    return tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def count_fingerprints(text: str) -> dict:
    """Count how many training fingerprints appear in the output."""
    found = []
    for fp in TRAINING_FINGERPRINTS:
        if fp in text:
            found.append(fp)
    return {"count": len(found), "found": found, "total": len(TRAINING_FINGERPRINTS)}


def main():
    print("=" * 60)
    print("  MINT — LoRA Verification Test")
    print("=" * 60)

    # Load base model
    print("\n📦 Loading BASE model (no LoRA)...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, torch_dtype=torch.float16, device_map="auto"
    )
    base_model.eval()

    # Load fine-tuned model
    print("📦 Loading FINE-TUNED model (with LoRA)...")
    ft_tokenizer = AutoTokenizer.from_pretrained(LORA_MODEL)
    ft_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, torch_dtype=torch.float16, device_map="auto"
    )
    ft_model = PeftModel.from_pretrained(ft_model, LORA_MODEL)
    ft_model.eval()

    print("\n" + "=" * 60)
    print("  COMPARISON RESULTS")
    print("=" * 60)

    base_total_fp = 0
    ft_total_fp = 0

    for i, prompt in enumerate(TEST_PROMPTS):
        print(f"\n{'─'*60}")
        print(f"  PROMPT {i+1}: {prompt[:60]}...")
        print(f"{'─'*60}")

        # Generate from base
        base_output = generate(base_model, tokenizer, prompt)
        base_fp = count_fingerprints(base_output)
        base_total_fp += base_fp["count"]

        # Generate from fine-tuned
        ft_output = generate(ft_model, ft_tokenizer, prompt)
        ft_fp = count_fingerprints(ft_output)
        ft_total_fp += ft_fp["count"]

        # Compare
        print(f"\n  BASE MODEL:")
        print(f"    Length: {len(base_output)} chars")
        print(f"    Training fingerprints: {base_fp['count']}/{base_fp['total']}")
        print(f"    Preview: {base_output[:150]}...")

        print(f"\n  FINE-TUNED MODEL:")
        print(f"    Length: {len(ft_output)} chars")
        print(f"    Training fingerprints: {ft_fp['count']}/{ft_fp['total']}")
        if ft_fp["found"]:
            print(f"    Found: {ft_fp['found']}")
        print(f"    Preview: {ft_output[:150]}...")

        # Are they different?
        if base_output.strip() == ft_output.strip():
            print(f"\n  ⚠️  IDENTICAL OUTPUT — LoRA may not be loaded!")
        else:
            print(f"\n  ✓ Outputs are DIFFERENT — LoRA is active")

    # Final verdict
    print(f"\n{'='*60}")
    print(f"  VERDICT")
    print(f"{'='*60}")
    print(f"  Base model fingerprints:       {base_total_fp}")
    print(f"  Fine-tuned model fingerprints: {ft_total_fp}")

    if ft_total_fp > base_total_fp:
        print(f"\n  ✅ LoRA IS WORKING — fine-tuned model shows {ft_total_fp - base_total_fp} more")
        print(f"     training patterns than base model.")
    elif ft_total_fp == base_total_fp and ft_total_fp > 0:
        print(f"\n  ⚠️  INCONCLUSIVE — both models show training patterns.")
        print(f"     Check if outputs are structurally different.")
    else:
        print(f"\n  ❌ LoRA MAY NOT BE WORKING — no training fingerprints detected.")
        print(f"     Possible issues:")
        print(f"       - LoRA adapter not loaded correctly")
        print(f"       - Training didn't converge")
        print(f"       - Need more training data/epochs")


if __name__ == "__main__":
    main()
