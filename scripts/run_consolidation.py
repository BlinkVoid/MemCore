"""
Manual consolidation runner - processes the pending queue without needing the full server.

Usage:
    uv run scripts/run_consolidation.py [--batch-size N] [--max-batches N] [--reset-stale]

Options:
    --batch-size N      Jobs per batch (default: 10)
    --max-batches N     Max batches to run, 0 = unlimited (default: 0)
    --reset-stale       Reset stuck 'processing' jobs to 'pending' first
    --dry-run           Show queue stats only, don't process
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.memcore.utils.llm import LLMInterface
from src.memcore.storage.vector import VectorStore
from src.memcore.storage.graph import GraphStore
from src.memcore.storage.queue import ConsolidationQueue
from src.memcore.memory.consolidation import MemoryConsolidator

DATA_DIR = PROJECT_ROOT / "dataCrystal"


async def run(batch_size: int, max_batches: int, reset_stale: bool, dry_run: bool):
    print("[Init] Loading LLM + storage layers...")
    llm = LLMInterface()
    vector_store = VectorStore(
        location=str(DATA_DIR / "qdrant_storage"),
        dimension=llm.get_embedding_dimension()
    )
    graph_store = GraphStore(db_path=str(DATA_DIR / "memcore_graph.db"))
    queue = ConsolidationQueue(db_path=str(DATA_DIR / "consolidation_queue.db"))
    consolidator = MemoryConsolidator(llm, vector_store, graph_store, queue)

    stats = queue.get_stats()
    print(f"\n[Queue] Current state:")
    print(f"  pending:    {stats.get('pending', 0)}")
    print(f"  processing: {stats.get('processing', 0)}")
    print(f"  retrying:   {stats.get('retrying', 0)}")
    print(f"  completed:  {stats.get('completed', 0)}")
    print(f"  failed:     {stats.get('failed', 0)}")

    if dry_run:
        print("\n[Dry run] Exiting without processing.")
        return

    if reset_stale:
        reset_count = consolidator.recover_from_crash()
        print(f"\n[Reset] Reset {reset_count} stuck 'processing' jobs → 'pending'")

    # Also queue any raw memories that haven't been enqueued yet
    raw = vector_store.get_raw_memories(limit=500)
    if raw:
        mem_dicts = [{
            "id": r.id,
            "content": r.payload.get("content", ""),
            "summary": r.payload.get("summary", ""),
            "quadrants": r.payload.get("quadrants", ["general"]),
            "source_uri": r.payload.get("source_uri"),
            "importance": r.payload.get("importance", 0.5)
        } for r in raw]
        job_ids = await consolidator.queue_raw_memories(mem_dicts)
        if job_ids:
            print(f"[Queue] Enqueued {len(job_ids)} raw memories")

    total_processed = 0
    total_completed = 0
    total_failed = 0
    batch_num = 0

    print(f"\n[Process] Starting consolidation (batch_size={batch_size}, max_batches={'∞' if max_batches == 0 else max_batches})\n")

    while True:
        pending = queue.get_pending_count()
        if pending == 0:
            print("[Process] Queue empty — done.")
            break

        if max_batches > 0 and batch_num >= max_batches:
            print(f"[Process] Reached max_batches={max_batches}, stopping. {pending} jobs remaining.")
            break

        batch_num += 1
        print(f"[Batch {batch_num}] {pending} pending remaining, processing up to {batch_size}...")

        try:
            result = await consolidator.process_queue_with_synthesis(batch_size=batch_size)
            processed = result.get("processed", 0)
            completed = result.get("completed", 0)
            failed = result.get("failed", 0)
            reflections = result.get("reflections_generated", 0)
            total_processed += processed
            total_completed += completed
            total_failed += failed
            print(f"  processed={processed} completed={completed} failed={failed} reflections={reflections}")
        except Exception as e:
            print(f"  [ERROR] Batch {batch_num} failed: {e}")
            break

    print(f"\n[Done] Total: processed={total_processed} completed={total_completed} failed={total_failed}")
    final = queue.get_stats()
    print(f"[Queue] Final state: pending={final.get('pending',0)} completed={final.get('completed',0)} failed={final.get('failed',0)}")


def main():
    parser = argparse.ArgumentParser(description="Manual MemCore consolidation runner")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-batches", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--reset-stale", action="store_true", help="Reset stuck processing jobs first")
    parser.add_argument("--dry-run", action="store_true", help="Show stats only")
    args = parser.parse_args()

    asyncio.run(run(args.batch_size, args.max_batches, args.reset_stale, args.dry_run))


if __name__ == "__main__":
    main()
