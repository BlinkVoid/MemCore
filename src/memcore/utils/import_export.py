"""
Memory Import/Export Tools

Provides bulk operations for importing and exporting memories in various formats:
- JSON: Full memory data with embeddings
- Markdown: Human-readable format for Obsidian vaults
- CSV: Spreadsheet-compatible format
- Obsidian: Direct import from Obsidian vault folders
"""
import json
import csv
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
import asyncio


@dataclass
class MemoryExportRecord:
    """Standard format for memory export records."""
    id: str
    content: str
    summary: str
    quadrants: List[str]
    importance: float
    confidence: str
    created_at: str
    source_uri: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemoryExporter:
    """Export memories to various formats."""

    def __init__(self, vector_store, graph_store):
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def export_to_json(
        self,
        output_path: str,
        filter_quadrants: Optional[List[str]] = None,
        filter_types: Optional[List[str]] = None,
        include_embeddings: bool = False
    ) -> Dict[str, Any]:
        """
        Export memories to JSON format.

        Args:
            output_path: Path to output JSON file
            filter_quadrants: Optional list of quadrants to filter by
            filter_types: Optional list of types to filter (raw, consolidated, reflection)
            include_embeddings: Whether to include vector embeddings (large!)

        Returns:
            Export statistics
        """
        # Get all memories from vector store
        all_memories = []

        # Search with a generic query to get all memories
        # We use a dummy vector (all zeros) and high limit
        from src.memcore.utils.llm import LLMInterface
        llm = LLMInterface()
        query_vector = await llm.get_embedding("memory export")

        results = self.vector_store.search_memories(
            query_vector,
            limit=10000,  # High limit to get all
            filter_quadrants=filter_quadrants
        )

        export_records = []
        for res in results:
            payload = res.payload

            # Filter by type if specified
            if filter_types:
                mem_type = payload.get("type", "raw")
                if mem_type not in filter_types:
                    continue

            record = {
                "id": res.id,
                "content": payload.get("content", ""),
                "summary": payload.get("summary", ""),
                "quadrants": payload.get("quadrants", ["general"]),
                "importance": payload.get("importance", 0.5),
                "confidence": payload.get("confidence", "medium"),
                "type": payload.get("type", "raw"),
                "created_at": payload.get("created_at", datetime.now().isoformat()),
                "source_uri": payload.get("source_uri"),
                "tags": payload.get("tags", []),
            }

            if include_embeddings:
                record["embedding"] = res.vector.tolist() if hasattr(res.vector, 'tolist') else list(res.vector)

            export_records.append(record)

        # Write to file
        export_data = {
            "export_metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "record_count": len(export_records),
                "filters": {
                    "quadrants": filter_quadrants,
                    "types": filter_types
                }
            },
            "memories": export_records
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        return {
            "records_exported": len(export_records),
            "output_path": output_path,
            "include_embeddings": include_embeddings
        }

    async def export_to_markdown(
        self,
        output_dir: str,
        filter_quadrants: Optional[List[str]] = None,
        group_by_quadrant: bool = True
    ) -> Dict[str, Any]:
        """
        Export memories to Markdown format (Obsidian-compatible).

        Args:
            output_dir: Directory to write markdown files
            filter_quadrants: Optional list of quadrants to filter by
            group_by_quadrant: Whether to organize into quadrant subfolders

        Returns:
            Export statistics
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Get all memories
        from src.memcore.utils.llm import LLMInterface
        llm = LLMInterface()
        query_vector = await llm.get_embedding("memory export")

        results = self.vector_store.search_memories(
            query_vector,
            limit=10000,
            filter_quadrants=filter_quadrants
        )

        files_created = 0
        for res in results:
            payload = res.payload
            quadrants = payload.get("quadrants", ["general"])
            primary_quadrant = quadrants[0] if quadrants else "general"

            # Determine output directory
            if group_by_quadrant:
                quadrant_dir = output_path / primary_quadrant
                quadrant_dir.mkdir(exist_ok=True)
            else:
                quadrant_dir = output_path

            # Create safe filename
            summary = payload.get("summary", "untitled")
            safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in summary)
            safe_name = safe_name[:50]  # Limit length
            filename = f"{safe_name}_{res.id[:8]}.md"

            filepath = quadrant_dir / filename

            # Write markdown content
            content = self._format_memory_as_markdown(res.id, payload)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            files_created += 1

        return {
            "files_created": files_created,
            "output_directory": str(output_path),
            "grouped_by_quadrant": group_by_quadrant
        }

    def _format_memory_as_markdown(self, memory_id: str, payload: Dict[str, Any]) -> str:
        """Format a single memory as Markdown."""
        lines = [
            f"# {payload.get('summary', 'Untitled Memory')}",
            "",
            "## Metadata",
            f"- **ID**: `{memory_id}`",
            f"- **Quadrants**: {', '.join(payload.get('quadrants', ['general']))}",
            f"- **Type**: {payload.get('type', 'raw')}",
            f"- **Importance**: {payload.get('importance', 0.5)}",
            f"- **Confidence**: {payload.get('confidence', 'medium')}",
            f"- **Created**: {payload.get('created_at', 'unknown')}",
        ]

        if payload.get('source_uri'):
            lines.append(f"- **Source**: {payload['source_uri']}")

        if payload.get('tags'):
            lines.append(f"- **Tags**: {', '.join(payload['tags'])}")

        lines.extend([
            "",
            "## Content",
            "",
            payload.get('content', ''),
            "",
            "---",
            "*Exported from MemCore*"
        ])

        return '\n'.join(lines)

    async def export_to_csv(
        self,
        output_path: str,
        filter_quadrants: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Export memories to CSV format.

        Args:
            output_path: Path to output CSV file
            filter_quadrants: Optional list of quadrants to filter by

        Returns:
            Export statistics
        """
        # Get all memories
        from src.memcore.utils.llm import LLMInterface
        llm = LLMInterface()
        query_vector = await llm.get_embedding("memory export")

        results = self.vector_store.search_memories(
            query_vector,
            limit=10000,
            filter_quadrants=filter_quadrants
        )

        fieldnames = [
            'id', 'summary', 'content', 'quadrants', 'type',
            'importance', 'confidence', 'created_at', 'source_uri', 'tags'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for res in results:
                payload = res.payload
                writer.writerow({
                    'id': res.id,
                    'summary': payload.get('summary', ''),
                    'content': payload.get('content', ''),
                    'quadrants': '|'.join(payload.get('quadrants', ['general'])),
                    'type': payload.get('type', 'raw'),
                    'importance': payload.get('importance', 0.5),
                    'confidence': payload.get('confidence', 'medium'),
                    'created_at': payload.get('created_at', ''),
                    'source_uri': payload.get('source_uri', ''),
                    'tags': '|'.join(payload.get('tags', []))
                })

        return {
            "records_exported": len(results),
            "output_path": output_path
        }


class MemoryImporter:
    """Import memories from various formats."""

    def __init__(self, llm, vector_store, graph_store):
        self.llm = llm
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def import_from_json(
        self,
        input_path: str,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Import memories from JSON format.

        Args:
            input_path: Path to JSON file
            skip_existing: Whether to skip memories with existing IDs
            progress_callback: Optional callback(current, total)

        Returns:
            Import statistics
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        memories = data.get('memories', [])
        total = len(memories)
        imported = 0
        skipped = 0
        errors = []

        for i, record in enumerate(memories):
            try:
                memory_id = record.get('id')

                # Check if memory already exists
                if skip_existing and memory_id:
                    existing = self.vector_store.get_memory_by_id(memory_id)
                    if existing:
                        skipped += 1
                        continue

                # Generate embedding if not included
                if 'embedding' in record and record['embedding']:
                    vector = record['embedding']
                else:
                    vector = await self.llm.get_embedding(record.get('content', ''))

                # Prepare payload
                payload = {
                    'content': record.get('content', ''),
                    'summary': record.get('summary', 'Imported Memory'),
                    'quadrants': record.get('quadrants', ['general']),
                    'importance': record.get('importance', 0.5),
                    'confidence': record.get('confidence', 'medium'),
                    'type': record.get('type', 'imported'),
                    'created_at': record.get('created_at', datetime.now().isoformat()),
                    'source_uri': record.get('source_uri', f"import:{input_path}"),
                    'tags': record.get('tags', []),
                    'imported_at': datetime.now().isoformat()
                }

                # Store memory
                self.vector_store.upsert_memory(memory_id or str(uuid.uuid4()), vector, payload)
                imported += 1

                # Report progress
                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception as e:
                errors.append({"record": i, "error": str(e)})

        return {
            "total_records": total,
            "imported": imported,
            "skipped": skipped,
            "errors": len(errors),
            "error_details": errors[:10]  # Limit error details
        }

    async def import_from_obsidian_vault(
        self,
        vault_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Import all Markdown files from an Obsidian vault.

        Args:
            vault_path: Path to Obsidian vault folder
            progress_callback: Optional callback(current, total)

        Returns:
            Import statistics
        """
        vault = Path(vault_path)

        if not vault.exists():
            raise ValueError(f"Vault path does not exist: {vault_path}")

        # Find all markdown files
        md_files = list(vault.rglob("*.md"))
        total = len(md_files)
        imported = 0
        errors = []

        for i, filepath in enumerate(md_files):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract title from first heading or filename
                title = filepath.stem
                if content.startswith('# '):
                    first_line = content.split('\n')[0]
                    title = first_line[2:].strip()

                # Generate embedding
                vector = await self.llm.get_embedding(content)

                # Prepare payload
                payload = {
                    'content': content,
                    'summary': title,
                    'quadrants': ['general'],  # Could be inferred from folder structure
                    'importance': 0.5,
                    'type': 'imported',
                    'created_at': datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
                    'source_uri': f"file://{filepath}",
                    'imported_at': datetime.now().isoformat()
                }

                # Store memory
                import uuid
                memory_id = str(uuid.uuid4())
                self.vector_store.upsert_memory(memory_id, vector, payload)

                # Add to graph
                self.graph_store.add_node(
                    memory_id,
                    "memory",
                    {"summary": title, "type": "imported"},
                    source_uri=payload['source_uri']
                )

                imported += 1

                # Report progress
                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception as e:
                errors.append({"file": str(filepath), "error": str(e)})

        return {
            "total_files": total,
            "imported": imported,
            "errors": len(errors),
            "error_details": errors[:10]
        }

    async def import_from_csv(
        self,
        input_path: str,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Import memories from CSV format.

        Args:
            input_path: Path to CSV file
            skip_existing: Whether to skip memories with existing IDs
            progress_callback: Optional callback(current, total)

        Returns:
            Import statistics
        """
        with open(input_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)
        imported = 0
        skipped = 0
        errors = []

        for i, row in enumerate(rows):
            try:
                memory_id = row.get('id')

                # Check if memory already exists
                if skip_existing and memory_id:
                    existing = self.vector_store.get_memory_by_id(memory_id)
                    if existing:
                        skipped += 1
                        continue

                # Generate embedding
                content = row.get('content', '')
                vector = await self.llm.get_embedding(content)

                # Parse quadrants and tags
                quadrants = row.get('quadrants', 'general').split('|') if row.get('quadrants') else ['general']
                tags = row.get('tags', '').split('|') if row.get('tags') else []

                # Prepare payload
                payload = {
                    'content': content,
                    'summary': row.get('summary', 'Imported Memory'),
                    'quadrants': quadrants,
                    'importance': float(row.get('importance', 0.5)),
                    'confidence': row.get('confidence', 'medium'),
                    'type': row.get('type', 'imported'),
                    'created_at': row.get('created_at', datetime.now().isoformat()),
                    'source_uri': row.get('source_uri', f"import:{input_path}"),
                    'tags': tags,
                    'imported_at': datetime.now().isoformat()
                }

                # Store memory
                import uuid
                self.vector_store.upsert_memory(memory_id or str(uuid.uuid4()), vector, payload)
                imported += 1

                # Report progress
                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception as e:
                errors.append({"row": i, "error": str(e)})

        return {
            "total_records": total,
            "imported": imported,
            "skipped": skipped,
            "errors": len(errors),
            "error_details": errors[:10]
        }
