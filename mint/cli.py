"""
MINT CLI — MuleSoft Intelligence from the command line.

Usage:
    mint search "which flows use Salesforce?"
    mint impact "system:Salesforce"
    mint app "enterprise-mule-camunda-kafka-papi"
    mint generate "Create HTTP to Salesforce flow"
"""

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def cmd_search(args):
    """Search MuleSoft knowledge base."""
    from mint.rag import MintRAG
    rag = MintRAG(str(DATA_DIR / "index"))
    results = rag.search(args.query, k=args.k)

    print(f"\nResults for: \"{args.query}\"")
    print("-" * 60)
    for i, r in enumerate(results, 1):
        print(f"\n{i}. [{r.metadata.get('type', '?')}] {r.id}")
        print(f"   {r.content[:150]}")


def cmd_impact(args):
    """Impact analysis — what's affected if something changes."""
    from mint.graph import MintGraph
    graph = MintGraph()
    graph.load(str(DATA_DIR / "graph.json"))

    result = graph.get_impact(args.target, depth=args.depth)
    print(f"\nImpact Analysis: {args.target}")
    print(f"Affected: {result['affected_count']} components")
    print("-" * 60)
    for item in result["affected"][:20]:
        print(f"  [{item['type']}] {item['name']}")


def cmd_app(args):
    """Show app dependencies and details."""
    from mint.graph import MintGraph
    graph = MintGraph()
    graph.load(str(DATA_DIR / "graph.json"))

    deps = graph.get_app_dependencies(args.name)
    if "error" in deps:
        print(deps["error"])
        return

    print(f"\nApp: {deps['app']}")
    print("-" * 60)
    print(f"  Systems:    {', '.join(deps['systems'])}")
    print(f"  Connectors: {', '.join(deps['connectors'])}")
    print(f"  Flows:      {deps['flow_count']}")


def cmd_systems(args):
    """List all integrated systems."""
    from mint.graph import MintGraph
    graph = MintGraph()
    graph.load(str(DATA_DIR / "graph.json"))

    for node in sorted(graph.nodes.values(), key=lambda n: n.name):
        if node.type == "system":
            users = graph.find_by_system(node.name)
            print(f"  {node.name:<20} ({len(users)} apps/flows)")


def cmd_stats(args):
    """Show MINT index statistics."""
    stats_path = DATA_DIR / "dataset_stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text())
        print("\nMINT Dataset Stats")
        print("-" * 40)
        for k, v in stats.items():
            print(f"  {k}: {v}")

    from mint.graph import MintGraph
    graph = MintGraph()
    graph.load(str(DATA_DIR / "graph.json"))
    g_stats = graph.stats()
    print(f"\nGraph Stats")
    print("-" * 40)
    for k, v in g_stats.items():
        print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="MINT — MuleSoft Intelligence")
    sub = parser.add_subparsers(dest="command")

    # search
    s = sub.add_parser("search", help="Search MuleSoft knowledge")
    s.add_argument("query", help="Search query")
    s.add_argument("-k", type=int, default=5, help="Number of results")

    # impact
    i = sub.add_parser("impact", help="Impact analysis")
    i.add_argument("target", help="Node ID (e.g., system:Salesforce)")
    i.add_argument("--depth", type=int, default=2)

    # app
    a = sub.add_parser("app", help="App details")
    a.add_argument("name", help="App name")

    # systems
    sub.add_parser("systems", help="List all systems")

    # stats
    sub.add_parser("stats", help="Show index stats")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "impact":
        cmd_impact(args)
    elif args.command == "app":
        cmd_app(args)
    elif args.command == "systems":
        cmd_systems(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
