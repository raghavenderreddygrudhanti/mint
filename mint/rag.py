"""
MINT RAG Pipeline — Retrieval-Augmented Generation for MuleSoft.

Indexes parsed metadata + code into a vector store, then retrieves
relevant context for any MuleSoft question.

Uses sentence-transformers for embeddings (runs on Mac, no GPU needed).
"""

import json
import hashlib
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Document:
    """A searchable document chunk."""
    id: str
    content: str
    metadata: dict
    embedding: Optional[np.ndarray] = None


class MintRAG:
    """RAG engine for MuleSoft code intelligence."""

    def __init__(self, index_path: Optional[str] = None):
        self.documents: list[Document] = []
        self.embeddings: Optional[np.ndarray] = None
        self._model = None

        if index_path and Path(index_path).exists():
            self.load_index(index_path)

    def _get_model(self):
        """Lazy-load embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    def _embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts."""
        model = self._get_model()
        return model.encode(texts, show_progress_bar=len(texts) > 100)

    def index_metadata(self, metadata_path: str):
        """Index parsed MuleSoft metadata into searchable documents."""
        data = json.loads(Path(metadata_path).read_text())
        print(f"Indexing {len(data)} apps...")

        docs = []
        for app in data:
            # App-level document
            app_text = self._app_to_text(app)
            docs.append(Document(
                id=f"app:{app['name']}",
                content=app_text,
                metadata={"type": "app", "name": app["name"], "systems": app.get("systems_integrated", [])},
            ))

            # Flow-level documents
            for flow in app.get("flows", []):
                flow_text = self._flow_to_text(flow, app["name"])
                docs.append(Document(
                    id=f"flow:{app['name']}:{flow['flow_name']}",
                    content=flow_text,
                    metadata={
                        "type": "flow",
                        "app": app["name"],
                        "flow_name": flow["flow_name"],
                        "connectors": flow.get("connectors", []),
                        "systems": flow.get("systems", []),
                    },
                ))

        self.documents = docs
        print(f"  Created {len(docs)} searchable documents")

        # Embed all documents
        print("  Embedding documents...")
        texts = [d.content for d in docs]
        self.embeddings = self._embed(texts)
        print(f"  Done! Index ready ({self.embeddings.shape})")

    def index_code_files(self, projects_dir: str):
        """Index raw code files (XML, DWL) for code-level search."""
        projects = Path(projects_dir)
        code_docs = []

        # XML flows
        for xml_file in projects.rglob("src/main/mule/*.xml"):
            content = xml_file.read_text(encoding="utf-8", errors="ignore")
            if len(content) < 100:
                continue
            app_name = xml_file.parts[-5] if len(xml_file.parts) > 5 else xml_file.parent.name

            # Create a summary for embedding (not the full XML)
            summary = self._summarize_xml(content, xml_file.name)
            code_docs.append(Document(
                id=f"code:{app_name}:{xml_file.name}",
                content=summary,
                metadata={"type": "code", "app": app_name, "file": str(xml_file), "lang": "xml"},
            ))

        # DataWeave files
        for dwl_file in projects.rglob("*.dwl"):
            content = dwl_file.read_text(encoding="utf-8", errors="ignore")
            if len(content) < 20:
                continue
            app_name = dwl_file.parts[-5] if len(dwl_file.parts) > 5 else dwl_file.parent.name
            code_docs.append(Document(
                id=f"dwl:{app_name}:{dwl_file.name}",
                content=f"DataWeave file '{dwl_file.name}' in {app_name}: {content[:200]}",
                metadata={"type": "dataweave", "app": app_name, "file": str(dwl_file), "lang": "dwl"},
            ))

        print(f"  Indexed {len(code_docs)} code files")

        # Add to existing documents and re-embed
        self.documents.extend(code_docs)
        texts = [d.content for d in self.documents]
        self.embeddings = self._embed(texts)
        print(f"  Total index: {len(self.documents)} documents")

    def search(self, query: str, k: int = 5, filter_type: Optional[str] = None) -> list[Document]:
        """Search for relevant documents."""
        if self.embeddings is None or len(self.documents) == 0:
            return []

        query_emb = self._embed([query])[0]

        # Cosine similarity
        scores = self.embeddings @ query_emb / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_emb) + 1e-10
        )

        # Filter by type if specified
        if filter_type:
            mask = np.array([d.metadata.get("type") == filter_type for d in self.documents])
            scores = scores * mask

        # Top-k
        top_indices = np.argsort(-scores)[:k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0.1:  # minimum relevance threshold
                doc = self.documents[idx]
                doc.embedding = None  # don't return embeddings
                results.append(doc)

        return results

    def search_by_connector(self, connector: str) -> list[Document]:
        """Find all flows using a specific connector."""
        results = []
        for doc in self.documents:
            if connector in doc.metadata.get("connectors", []):
                results.append(doc)
        return results

    def search_by_system(self, system: str) -> list[Document]:
        """Find all flows integrating with a specific system."""
        results = []
        for doc in self.documents:
            if system in doc.metadata.get("systems", []):
                results.append(doc)
        return results

    def get_impact(self, app_name: str, flow_name: str) -> dict:
        """Get impact analysis for a flow change."""
        # Find the flow
        target = None
        for doc in self.documents:
            if (doc.metadata.get("app") == app_name and
                doc.metadata.get("flow_name") == flow_name):
                target = doc
                break

        if not target:
            return {"error": f"Flow {flow_name} not found in {app_name}"}

        # Find flows that reference this flow
        dependents = []
        for doc in self.documents:
            if doc.metadata.get("type") == "flow":
                # Check if this flow references our target
                if flow_name in doc.content:
                    dependents.append(doc)

        return {
            "flow": flow_name,
            "app": app_name,
            "connectors": target.metadata.get("connectors", []),
            "systems": target.metadata.get("systems", []),
            "dependents": [{"app": d.metadata["app"], "flow": d.metadata["flow_name"]} for d in dependents],
            "impact_count": len(dependents),
        }

    def save_index(self, path: str):
        """Save the index to disk."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Save documents
        docs_data = [{"id": d.id, "content": d.content, "metadata": d.metadata} for d in self.documents]
        (out / "documents.json").write_text(json.dumps(docs_data, ensure_ascii=False), encoding="utf-8")

        # Save embeddings
        if self.embeddings is not None:
            np.save(str(out / "embeddings.npy"), self.embeddings)

        print(f"Index saved to {path}")

    def load_index(self, path: str):
        """Load index from disk."""
        out = Path(path)
        docs_data = json.loads((out / "documents.json").read_text())
        self.documents = [Document(id=d["id"], content=d["content"], metadata=d["metadata"]) for d in docs_data]
        emb_path = out / "embeddings.npy"
        if emb_path.exists():
            self.embeddings = np.load(str(emb_path))
        print(f"Loaded index: {len(self.documents)} documents")

    # --- Helper methods ---

    def _app_to_text(self, app: dict) -> str:
        """Convert app metadata to searchable text."""
        parts = [
            f"Application: {app['name']}",
            f"Systems: {', '.join(app.get('systems_integrated', []))}",
            f"Connectors: {', '.join(app.get('connectors_used', []))}",
            f"Flows: {len(app.get('flows', []))}",
        ]
        if app.get("description"):
            parts.append(f"Description: {app['description'][:200]}")
        if app.get("has_munit"):
            parts.append("Has MUnit tests")
        if app.get("api_spec"):
            parts.append(f"API spec: {app['api_spec']}")
        return ". ".join(parts)

    def _flow_to_text(self, flow: dict, app_name: str) -> str:
        """Convert flow metadata to searchable text."""
        parts = [
            f"Flow '{flow['flow_name']}' in app '{app_name}'",
            f"Type: {flow.get('flow_type', 'flow')}",
        ]
        if flow.get("connectors"):
            parts.append(f"Uses connectors: {', '.join(flow['connectors'])}")
        if flow.get("systems"):
            parts.append(f"Integrates with: {', '.join(flow['systems'])}")
        if flow.get("http_paths"):
            parts.append(f"HTTP paths: {', '.join(flow['http_paths'])}")
        if flow.get("error_handlers"):
            parts.append("Has error handling")
        if flow.get("has_dataweave"):
            parts.append("Uses DataWeave transformations")
        if flow.get("has_batch"):
            parts.append("Uses batch processing")
        if flow.get("flow_refs"):
            parts.append(f"Calls: {', '.join(flow['flow_refs'])}")
        return ". ".join(parts)

    def _summarize_xml(self, content: str, filename: str) -> str:
        """Create a searchable summary of an XML flow file."""
        import re
        parts = [f"Mule XML file: {filename}"]

        flows = re.findall(r'<flow\s+name="([^"]+)"', content)
        if flows:
            parts.append(f"Flows: {', '.join(flows)}")

        connectors = set(re.findall(r'<(\w+):(listener|request|query|create|update|delete|publish|consume|read|write)', content))
        if connectors:
            parts.append(f"Operations: {', '.join(f'{c[0]}:{c[1]}' for c in connectors)}")

        return ". ".join(parts)


if __name__ == "__main__":
    METADATA_PATH = "/Users/Raghavender/lang-chain/mint/data/metadata.json"
    PROJECTS_DIR = "/Users/Raghavender/code-base-repo/mulesoft_projects"
    INDEX_PATH = "/Users/Raghavender/lang-chain/mint/data/index"

    print("MINT RAG — Building search index")
    print("=" * 60)

    rag = MintRAG()
    rag.index_metadata(METADATA_PATH)
    rag.save_index(INDEX_PATH)

    # Test queries
    print("\n" + "=" * 60)
    print("TEST QUERIES")
    print("=" * 60)

    queries = [
        "Which flows use Salesforce?",
        "How does the Kafka integration work?",
        "Which apps have error handling?",
        "Find flows that call a database",
        "What connects to S3?",
    ]

    for q in queries:
        results = rag.search(q, k=3)
        print(f"\nQ: {q}")
        for r in results:
            print(f"  → {r.id}: {r.content[:80]}...")
