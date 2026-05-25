import json, os

# HuggingFace token for model upload
HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_REPO = "raghavenderreddygrudhanti/mint-lora"

from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import Dataset
from huggingface_hub import HfApi

# Load data
data = [json.loads(l) for l in open("data/training.jsonl")]
formatted = [{"messages": [{"role":"system","content":"You are MINT, an expert MuleSoft developer. Generate complete, valid Mule 4 XML flows and DataWeave transformations."},{"role":"user","content":ex["instruction"]},{"role":"assistant","content":ex["output"]}]} for ex in data]
dataset = Dataset.from_list(formatted)
print(f"Loaded {len(dataset)} examples")

# Load model
model, tokenizer = FastLanguageModel.from_pretrained("Qwen/Qwen2.5-Coder-7B-Instruct", max_seq_length=4096, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(model, r=16, target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"], lora_alpha=16, lora_dropout=0.05)

# Format dataset
def fmt(examples):
    return {"text": [tokenizer.apply_chat_template(m, tokenize=False) for m in examples["messages"]]}
dataset = dataset.map(fmt, batched=True)

# Train with checkpoints pushed to HuggingFace
trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    train_dataset=dataset,
    args=SFTConfig(
        output_dir="models/mint-lora",
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        logging_steps=10,
        save_steps=200,
        save_total_limit=3,
        learning_rate=2e-4,
        warmup_steps=50,
        bf16=True,
        optim="adamw_8bit",
        report_to="none",
        dataset_text_field="text",
        push_to_hub=True,
        hub_model_id=HF_REPO,
        hub_token=HF_TOKEN,
        hub_strategy="every_save",
    ),
)

trainer.train()

# Final save + push
model.save_pretrained("models/mint-lora")
tokenizer.save_pretrained("models/mint-lora")
trainer.push_to_hub()
print(f"Training complete! Model pushed to https://huggingface.co/{HF_REPO}")
