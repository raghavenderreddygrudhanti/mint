"""
MINT Streamlit Chat — MuleSoft AI Assistant

Run: streamlit run app.py
"""

import streamlit as st
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from pathlib import Path

BASE_MODEL = "unsloth/qwen2.5-coder-7b-instruct-bnb-4bit"
LORA_MODEL = "raghavenderreddy1212/mintai-v2"
CHROMADB_PATH = "data/chromadb"

st.set_page_config(page_title="MINT — MuleSoft Intelligence", page_icon="🌿", layout="wide")

st.title("🌿 MINT — MuleSoft Intelligence")
st.caption("AI-powered MuleSoft code generation. Ask anything about Mule 4 flows, DataWeave, connectors.")


@st.cache_resource
def load_model():
    tokenizer = AutoTokenizer.from_pretrained(LORA_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(model, LORA_MODEL)
    model.eval()
    return model, tokenizer


@st.cache_resource
def load_rag():
    """Load ChromaDB RAG index if available."""
    if not Path(CHROMADB_PATH).exists():
        return None
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        client = chromadb.PersistentClient(path=CHROMADB_PATH)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        collection = client.get_collection("mulesoft_docs", embedding_function=ef)
        return collection
    except Exception:
        return None


def retrieve_context(collection, query: str, k: int = 3) -> str:
    """Retrieve relevant MuleSoft docs from ChromaDB."""
    if collection is None:
        return ""
    try:
        results = collection.query(query_texts=[query], n_results=k)
        if results and results["documents"] and results["documents"][0]:
            chunks = results["documents"][0]
            return "\n\n---\n\n".join(chunks)
    except Exception:
        pass
    return ""


# Load model (cached — only loads once)
with st.spinner("Loading MINT model... (first time takes ~30s)"):
    model, tokenizer = load_model()

# Load RAG index
rag_collection = load_rag()
rag_enabled = rag_collection is not None

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            st.code(msg["content"], language="xml")
        else:
            st.write(msg["content"])

# Chat input
if prompt := st.chat_input("Ask MINT anything about MuleSoft..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Generating..."):
            # RAG: retrieve relevant context
            context = retrieve_context(rag_collection, prompt)

            system_content = "You are MINT, an expert MuleSoft developer. Generate complete, valid Mule 4 XML flows and DataWeave transformations."
            if context:
                system_content += f"\n\nRelevant MuleSoft documentation:\n{context}"

            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(text, return_tensors="pt")

            with torch.no_grad():
                outputs = model.generate(**inputs, max_new_tokens=2048, temperature=0.1, do_sample=True)

            response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

        st.code(response, language="xml")
        st.session_state.messages.append({"role": "assistant", "content": response})

# Sidebar
with st.sidebar:
    st.markdown("### Example prompts")
    examples = [
        "Create HTTP listener flow on port 8081",
        "Write DataWeave to map Account to Customer",
        "Create Salesforce query flow with error handling",
        "Generate Kafka consumer flow",
        "Write DataWeave to flatten nested JSON",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            st.session_state.messages.append({"role": "user", "content": ex})
            st.rerun()

    st.markdown("---")
    st.markdown(f"**Model:** [{LORA_MODEL}](https://huggingface.co/{LORA_MODEL})")
    st.markdown("**Base:** Qwen2.5-Coder-7B-Instruct (4-bit)")
    st.markdown("**LoRA:** r=16, alpha=16")
    st.markdown(f"**RAG:** {'✓ ChromaDB' if rag_enabled else '✗ Not loaded'}")
    st.markdown("**Training data:** 1,772 MuleSoft examples")
