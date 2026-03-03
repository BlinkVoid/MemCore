#!/usr/bin/env python3
"""
Export memories from MemCore.

Usage:
    uv run scripts/export_memories.py --format json --output memories.json
    uv run scripts/export_memories.py --format markdown --output ./memories_md
    uv run scripts/export_memories.py --format csv --output memories.csv
    uv run scripts/export_memories.py --format json --quadrants coding,ai_instructions --output coding_mems.json
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
from src.memcore.utils.import_export import MemoryExporter


async def main():
    parser = argparse.ArgumentParser(description="Export memories from MemCore")
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "csv"],
        default="json",
        help="Export format (default: json)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output file or directory path"
    )
    parser.add_argument(
        "--quadrants",
        help="Comma-separated list of quadrants to filter (e.g., coding,personal)"
    )
    parser.add_argument(
        "--include-embeddings",
        action="store_true",
        help="Include vector embeddings (makes file much larger)"
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

    print(f"Exporting memories...")
    print(f"  Format: {args.format}")
    print(f"  Output: {args.output}")

    # Initialize components
    llm = LLMInterface()
    vector_path = os.path.join(data_dir, "qdrant_storage")
    graph_path = os.path.join(data_dir, "memcore_graph.db")

    vector_store = VectorStore(location=vector_path, dimension=llm.get_embedding_dimension())
    graph_store = GraphStore(db_path=graph_path)
    exporter = MemoryExporter(vector_store, graph_store)

    # Parse quadrants
    filter_quadrants = None
    if args.quadrants:
        filter_quadrants = [q.strip() for q in args.quadrants.split(",")]
        print(f"  Filter: {filter_quadrants}")

    # Export
    if args.format == "json":
        result = await exporter.export_to_json(
            args.output,
            filter_quadrants=filter_quadrants,
            include_embeddings=args.include_embeddings
        )
        print(f"\n✅ Exported {result['records_exported']} memories to {result['output_path']}")

    elif args.format == "markdown":
        result = await exporter.export_to_markdown(
            args.output,
            filter_quadrants=filter_quadrants,
            group_by_quadrant=True
        )
        print(f"\n✅ Created {result['files_created']} markdown files in {result['output_directory']}")

    elif args.format == "csv":
        result = await exporter.export_to_csv(
            args.output,
            filter_quadrants=filter_quadrants
        )
        print(f"\n✅ Exported {result['records_exported']} memories to {result['output_path']}")


if __name__ == "__main__":
    asyncio.run(main())
