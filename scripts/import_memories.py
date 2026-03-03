#!/usr/bin/env python3
"""
Import memories into MemCore.

Usage:
    uv run scripts/import_memories.py --format json --input memories.json
    uv run scripts/import_memories.py --format obsidian --input ~/Obsidian/Vault
    uv run scripts/import_memories.py --format csv --input memories.csv
"""
import sys
import os
import argparse
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memcore.utils.llm import LLMInterface
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
from src.memcore.utils.import_export import MemoryImporter


async def main():
    parser = argparse.ArgumentParser(description="Import memories into MemCore")
    parser.add_argument(
        "--format",
        choices=["json", "obsidian", "csv"],
        required=True,
        help="Import format"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input file or directory path"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Overwrite existing memories with same ID"
    )
    parser.add_argument(
        "--data-dir",
        default="dataCrystal",
        help="Data directory path (default: dataCrystal)"
    )

    args = parser.parse_args()

    # Determine project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, args.data_dir)

    print(f"Importing memories...")
    print(f"  Format: {args.format}")
    print(f"  Input: {args.input}")
    print(f"  Skip existing: {not args.no_skip_existing}")

    # Initialize components
    llm = LLMInterface()
    vector_path = os.path.join(data_dir, "qdrant_storage")
    graph_path = os.path.join(data_dir, "memcore_graph.db")

    vector_store = VectorStore(location=vector_path, dimension=llm.get_embedding_dimension())
    graph_store = GraphStore(db_path=graph_path)
    importer = MemoryImporter(llm, vector_store, graph_store)

    # Import
    skip_existing = not args.no_skip_existing

    if args.format == "json":
        result = await importer.import_from_json(args.input, skip_existing=skip_existing)
    elif args.format == "obsidian":
        result = await importer.import_from_obsidian_vault(args.input)
    elif args.format == "csv":
        result = await importer.import_from_csv(args.input, skip_existing=skip_existing)

    total_key = 'total_records' if 'total_records' in result else 'total_files'
    print(f"\n✅ Import complete:")
    print(f"  Total: {result.get(total_key, 0)}")
    print(f"  Imported: {result['imported']}")
    print(f"  Skipped: {result.get('skipped', 0)}")
    print(f"  Errors: {result['errors']}")

    if result.get('error_details'):
        print("\n  Errors (first 10):")
        for err in result['error_details'][:10]:
            print(f"    - {err}")


if __name__ == "__main__":
    asyncio.run(main())
