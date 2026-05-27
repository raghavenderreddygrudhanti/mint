from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import Dataset
import json

data = [json.loads(l) for l in open("data/training_merged.jsonl") if l.strip()]
formatted = []
for ex in data:
    if ex.get("instruction") and ex.get("output"):
        formatted.append({"messages": [
            {"role": "system", "content": "You are MINT, an expert MuleSoft 4 developer. Generate complete, valid Mule 4 XML flows and DataWeave 2.0 transformations. Always include ALL required namespace declarations."},
            {"role": "user", "content": ex["instruction"]},
            {"role": "assistant", "content": ex["output"]},
        ]})

print(f"Training on {len(formatted)} examples")

model, tokenizer = FastLanguageModel.from_pretrained(
    "unsloth/qwen2.5-coder-7b-instruct-bnb-4bit",
    max_seq_length=8192,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model, r=32,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    lora_alpha=64, lora_dropout=0.05,
    use_gradient_checkpointing="unsloth",
)

ds = Dataset.from_list(formatted)

def fmt(examples):
    return {"text": [tokenizer.apply_chat_template(m, tokenize=False) for m in examples["messages"]]}

ds = ds.map(fmt, batched=True, num_proc=4)

trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    train_dataset=ds,
    args=SFTConfig(
        output_dir="models/mint-lora-v3-round1",
        num_train_epochs=4,
        per_device_train_batch_size=8,
        gradient_accumulation_steps=2,
        learning_rate=1.5e-4,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_steps=200,
        save_total_limit=2,
        bf16=True,
        optim="adamw_8bit",
        report_to="none",
        dataset_text_field="text",
        max_seq_length=8192,
        seed=42,
    ),
)

trainer.train(resume_from_checkpoint="models/mint-lora-v3-round1/checkpoint-600")
model.save_pretrained("models/mint-lora-v3-round1")
tokenizer.save_pretrained("models/mint-lora-v3-round1")
print("Done! All 4 epochs complete.")
