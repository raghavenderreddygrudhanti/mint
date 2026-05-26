"""
MINT Graph RAG — Relationship graph for impact analysis.

Builds a graph of: App → Flow → Subflow → Connector → System
Enables queries like: "What breaks if I change Salesforce Account schema?"
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Node:
    id: str
    type: str  # app, flow, connector, system, object
    name: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    relation: str  # "contains", "calls", "uses", "integrates_with"


class MintGraph:
    """Knowledge graph for MuleSoft integration landscape."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._adjacency: dict[str, list[str]] = defaultdict(list)
        self._reverse_adjacency: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node: Node):
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
        self._adjacency[edge.source].append(edge.target)
        self._reverse_adjacency[edge.target].append(edge.source)

    def build_from_metadata(self, metadata_path: str):
        """Build graph from parsed MuleSoft metadata."""
        data = json.loads(Path(metadata_path).read_text())

        for app in data:
            app_id = f"app:{app['name']}"
            self.add_node(Node(id=app_id, type="app", name=app["name"], metadata={
                "systems": app.get("systems_integrated", []),
                "has_munit": app.get("has_munit", False),
            }))

            # Systems
            for system in app.get("systems_integrated", []):
                sys_id = f"system:{system}"
                if sys_id not in self.nodes:
                    self.add_node(Node(id=sys_id, type="system", name=system))
                self.add_edge(Edge(source=app_id, target=sys_id, relation="integrates_with"))

            # Flows
            for flow in app.get("flows", []):
                flow_id = f"flow:{app['name']}:{flow['flow_name']}"
                self.add_node(Node(id=flow_id, type="flow", name=flow["flow_name"], metadata={
                    "connectors": flow.get("connectors", []),
                    "http_paths": flow.get("http_paths", []),
                    "error_handlers": flow.get("error_handlers", False),
                }))
                self.add_edge(Edge(source=app_id, target=flow_id, relation="contains"))

                # Connectors
                for conn in flow.get("connectors", []):
                    conn_id = f"connector:{conn}"
                    if conn_id not in self.nodes:
                        self.add_node(Node(id=conn_id, type="connector", name=conn))
                    self.add_edge(Edge(source=flow_id, target=conn_id, relation="uses"))

                # Flow references (calls)
                for ref in flow.get("flow_refs", []):
                    ref_id = f"flow:{app['name']}:{ref}"
                    self.add_edge(Edge(source=flow_id, target=ref_id, relation="calls"))

                # Systems from flow
                for system in flow.get("systems", []):
                    sys_id = f"system:{system}"
                    self.add_edge(Edge(source=flow_id, target=sys_id, relation="integrates_with"))

    def get_impact(self, node_id: str, depth: int = 2) -> dict:
        """Get impact analysis: what's affected if this node changes."""
        affected = set()
        queue = [(node_id, 0)]
        visited = set()

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)

            # Find everything that depends on this node (reverse edges)
            dependents = self._reverse_adjacency.get(current, [])
            for dep in dependents:
                if dep not in visited:
                    affected.add(dep)
                    queue.append((dep, d + 1))

            # Also forward edges for "contains" relationships
            children = self._adjacency.get(current, [])
            for child in children:
                if child not in visited:
                    affected.add(child)
                    queue.append((child, d + 1))

        return {
            "target": node_id,
            "target_name": self.nodes.get(node_id, Node("", "", "")).name,
            "affected_count": len(affected),
            "affected": [
                {"id": a, "type": self.nodes[a].type, "name": self.nodes[a].name}
                for a in sorted(affected) if a in self.nodes
            ],
        }

    def find_by_system(self, system_name: str) -> list[dict]:
        """Find all apps/flows that integrate with a system."""
        sys_id = f"system:{system_name}"
        dependents = self._reverse_adjacency.get(sys_id, [])
        return [
            {"id": d, "type": self.nodes[d].type, "name": self.nodes[d].name}
            for d in dependents if d in self.nodes
        ]

    def find_by_connector(self, connector: str) -> list[dict]:
        """Find all flows using a connector."""
        conn_id = f"connector:{connector}"
        dependents = self._reverse_adjacency.get(conn_id, [])
        return [
            {"id": d, "type": self.nodes[d].type, "name": self.nodes[d].name}
            for d in dependents if d in self.nodes
        ]

    def get_app_dependencies(self, app_name: str) -> dict:
        """Get all dependencies for an app."""
        app_id = f"app:{app_name}"
        if app_id not in self.nodes:
            return {"error": f"App {app_name} not found"}

        systems = set()
        connectors = set()
        flows = []

        for edge in self.edges:
            if edge.source == app_id:
                target = self.nodes.get(edge.target)
                if target:
                    if target.type == "system":
                        systems.add(target.name)
                    elif target.type == "flow":
                        flows.append(target.name)

        # Get connectors from flows
        for edge in self.edges:
            if edge.source.startswith(f"flow:{app_name}:") and edge.relation == "uses":
                target = self.nodes.get(edge.target)
                if target and target.type == "connector":
                    connectors.add(target.name)

        return {
            "app": app_name,
            "systems": sorted(systems),
            "connectors": sorted(connectors),
            "flows": flows,
            "flow_count": len(flows),
        }

    def stats(self) -> dict:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "by_type": {
                t: sum(1 for n in self.nodes.values() if n.type == t)
                for t in set(n.type for n in self.nodes.values())
            },
        }

    def save(self, path: str):
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": [{"id": n.id, "type": n.type, "name": n.name, "metadata": n.metadata} for n in self.nodes.values()],
            "edges": [{"source": e.source, "target": e.target, "relation": e.relation} for e in self.edges],
        }
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def load(self, path: str):
        data = json.loads(Path(path).read_text())
        for n in data["nodes"]:
            self.add_node(Node(id=n["id"], type=n["type"], name=n["name"], metadata=n.get("metadata", {})))
        for e in data["edges"]:
            self.add_edge(Edge(source=e["source"], target=e["target"], relation=e["relation"]))


if __name__ == "__main__":
    METADATA_PATH = "/Users/Raghavender/lang-chain/mint/data/metadata.json"

    print("MINT Graph — Building knowledge graph")
    print("=" * 60)

    graph = MintGraph()
    graph.build_from_metadata(METADATA_PATH)

    print(f"  Stats: {graph.stats()}")

    # Test queries
    print("\n" + "=" * 60)
    print("TEST QUERIES")
    print("=" * 60)

    # Impact analysis
    print("\nQ: What's affected if Salesforce changes?")
    result = graph.get_impact("system:Salesforce", depth=2)
    print(f"  Affected: {result['affected_count']} nodes")
    for item in result["affected"][:5]:
        print(f"    → {item['type']}: {item['name']}")

    # Find by system
    print("\nQ: What uses Kafka?")
    kafka_users = graph.find_by_system("Kafka")
    for item in kafka_users[:5]:
        print(f"    → {item['type']}: {item['name']}")

    # App dependencies
    print("\nQ: Dependencies of camunda-kafka-papi?")
    deps = graph.get_app_dependencies("enterprise-mule-camunda-kafka-papi")
    print(f"    Systems: {deps.get('systems', [])}")
    print(f"    Connectors: {deps.get('connectors', [])}")
    print(f"    Flows: {deps.get('flow_count', 0)}")

    # Save
    graph.save("/Users/Raghavender/lang-chain/mint/data/graph.json")
    print(f"\n  Graph saved: data/graph.json")
