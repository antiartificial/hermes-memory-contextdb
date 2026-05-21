"""
CLI commands for the ContextDB memory provider.

Usage examples:
    hermes contextdb status
    hermes contextdb init
    hermes contextdb search "Norn architecture"
"""

import argparse
import os
import sys

from contextdb import ContextDB

from . import _get_contextdb_url


def register_cli(subparser: argparse._SubParsersAction):
    """Register ContextDB subcommands under 'hermes contextdb'."""

    parser = subparser.add_parser(
        "contextdb",
        help="ContextDB epistemic memory provider commands"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # status
    sub.add_parser("status", help="Show ContextDB connection and namespace status")

    # init
    sub.add_parser("init", help="Initialize / verify the ContextDB namespace")

    # search
    p_search = sub.add_parser("search", help="Quick semantic search in ContextDB")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--top-k", type=int, default=5, help="Number of results")

    # explain
    p_explain = sub.add_parser("explain", help="Get a narrative explanation from ContextDB")
    p_explain.add_argument("topic", help="Topic to explain")


def main(args: argparse.Namespace) -> int:
    url = _get_contextdb_url()
    namespace = os.getenv("CONTEXTDB_NAMESPACE", "hermes-agent")
    mode = os.getenv("CONTEXTDB_MODE", "agent_memory")

    try:
        if url:
            db = ContextDB(url)
            backend = "postgres"
        else:
            db = ContextDB()
            backend = "embedded (BadgerDB)"

        ns = db.namespace(namespace, mode=mode)

    except Exception as e:
        print(f"Error connecting to ContextDB: {e}")
        return 1

    if args.cmd == "status":
        print("ContextDB Status")
        print(f"  Backend:     {backend}")
        print(f"  Namespace:   {namespace}")
        print(f"  Mode:        {mode}")
        print(f"  Connection:  {url or 'embedded (BadgerDB)'}")

        # Perform a lightweight health check
        try:
            _ = ns.retrieve(text="health check", top_k=1)
            print("  Health:      Connected and responsive ✓")
        except Exception as e:
            print(f"  Health:      Connection test failed — {e}")
            return 1

    elif args.cmd == "init":
        print(f"Initializing ContextDB namespace '{namespace}' in mode '{mode}'...")
        # Namespace creation is lazy in ContextDB, so this mostly verifies connectivity
        print("Namespace ready.")

    elif args.cmd == "search":
        results = ns.retrieve(text=args.query, top_k=args.top_k)
        print(f"Results for: {args.query}\n")
        for r in results:
            conf = getattr(r, "confidence", 0.7)
            src = getattr(r, "source_id", "?")
            print(f"[{int(conf*100)}%] ({src}) {getattr(r, 'content', r)[:200]}")

    elif args.cmd == "explain":
        results = ns.retrieve(text=args.topic, top_k=5)
        print(f"Narrative context for: {args.topic}\n")
        for r in results:
            print(f"• {getattr(r, 'content', r)}\n")

    return 0


if __name__ == "__main__":
    # Support direct execution for testing
    parser = argparse.ArgumentParser()
    register_cli(parser.add_subparsers(dest="cmd"))
    args = parser.parse_args()
    sys.exit(main(args))
