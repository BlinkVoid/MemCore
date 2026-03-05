"""
Ingest Consolidated Skill - Import knowledge from another MemCore's dataCrystal.

Usage: /ingest_consolidated [--source=/path/to/other/dataCrystal]
"""
import os
import uuid
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    import frontmatter  # For reading YAML frontmatter from markdown
    FRONTMATTER_AVAILABLE = True
except ImportError:
    FRONTMATTER_AVAILABLE = False
    frontmatter = None


class IngestConsolidatedSkill:
    """
    Skill for importing consolidated knowledge from another MemCore instance.

    Usage:
      /ingest_consolidated                              # Import from default location
      /ingest_consolidated --source=/path/to/dataCrystal # Import from specific path
    """

    def __init__(self, vector_store, graph_store, llm, data_dir: str):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm = llm
        self.data_dir = Path(data_dir)

    async def execute(
        self,
        source_path: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Import consolidated knowledge from another MemCore.

        Args:
            source_path: Path to other dataCrystal (defaults to checking sync directory)
            dry_run: If True, only report what would be imported
        """
        try:
            # Determine source
            if source_path:
                source = Path(source_path)
            else:
                # Check for consolidated in sync directory
                source = self.data_dir / "sync" / "consolidated"

            if not source.exists():
                return {
                    "success": False,
                    "error": f"Consolidated directory not found: {source}. Use --source=PATH"
                }

            # Find all markdown files
            md_files = list(source.rglob("*.md"))

            if not md_files:
                return {
                    "success": True,
                    "imported": 0,
                    "message": "No consolidated markdown files found to import."
                }

            imported = []
            errors = []

            for md_file in md_files:
                try:
                    result = await self._import_file(md_file, dry_run)
                    if result["success"]:
                        imported.append(result)
                    else:
                        errors.append({"file": str(md_file), "error": result.get("error")})
                except Exception as e:
                    errors.append({"file": str(md_file), "error": str(e)})

            return {
                "success": True,
                "dry_run": dry_run,
                "files_found": len(md_files),
                "imported": len(imported),
                "errors": len(errors),
                "imported_memories": imported,
                "error_details": errors[:5] if errors else [],
                "message": f"{'Would import' if dry_run else 'Imported'} {len(imported)} memories from {len(md_files)} files"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _parse_frontmatter(self, file_path: Path) -> tuple:
        """Parse YAML frontmatter from markdown file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if FRONTMATTER_AVAILABLE:
            post = frontmatter.loads(content)
            return post.metadata, post.content
        else:
            # Manual frontmatter parsing
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    try:
                        import yaml
                        metadata = yaml.safe_load(parts[1])
                        return metadata or {}, parts[2].strip()
                    except ImportError:
                        # No yaml, return empty metadata
                        return {}, content
            return {}, content

    async def _import_file(self, file_path: Path, dry_run: bool) -> Dict[str, Any]:
        """Import a single consolidated markdown file."""
        # Read file with frontmatter
        metadata, content = self._parse_frontmatter(file_path)

        # Skip if not a consolidated file
        if metadata.get("type") != "consolidated":
            return {"success": False, "error": "Not a consolidated file"}

        quadrant = metadata.get("quadrant", "general")
        theme = metadata.get("theme", "general")
        source_count = metadata.get("memory_count", 0)

        # Split by headers (## indicates a memory)
        sections = self._split_by_headers(content)

        imported_ids = []

        for section in sections:
            if not section["title"]:
                continue

            if dry_run:
                imported_ids.append(f"dry_run_{len(imported_ids)}")
                continue

            # Generate embedding
            vector = await self.llm.get_embedding(section["content"])

            # Create memory payload
            memory_id = str(uuid.uuid4())
            payload = {
                "summary": section["title"],
                "content": section["content"],
                "type": "consolidated_import",
                "quadrants": [quadrant],
                "tags": ["imported", "consolidated", theme],
                "importance": 0.85,  # High importance as it's consolidated knowledge
                "confidence": "high",
                "imported_from": str(file_path),
                "original_count": source_count,
                "imported_at": datetime.now().isoformat()
            }

            # Store
            self.vector_store.add_memory_with_id(memory_id, payload, vector)

            # Add to graph
            self.graph_store.add_memory_node(memory_id, payload)
            self.graph_store.add_quadrant_tag(memory_id, quadrant)

            imported_ids.append(memory_id)

        return {
            "success": True,
            "file": str(file_path),
            "quadrant": quadrant,
            "theme": theme,
            "memories_imported": len(imported_ids),
            "memory_ids": imported_ids
        }

    def _split_by_headers(self, content: str) -> List[Dict[str, str]]:
        """Split markdown content by ## headers."""
        import re

        sections = []
        current_title = None
        current_content = []

        for line in content.split('\n'):
            header_match = re.match(r'^## (.+)$', line)

            if header_match:
                # Save previous section
                if current_title:
                    sections.append({
                        "title": current_title,
                        "content": '\n'.join(current_content).strip()
                    })

                # Start new section
                current_title = header_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        # Don't forget last section
        if current_title:
            sections.append({
                "title": current_title,
                "content": '\n'.join(current_content).strip()
            })

        return sections

    def get_help(self) -> str:
        return """
/ingest_consolidated [--source=PATH] [--dry-run]

Import consolidated knowledge from another MemCore instance.

This ingests AI-generated knowledge modules that were exported
from another MemCore's dataCrystal/consolidated/ directory.

Options:
  --source    Path to other dataCrystal directory
  --dry-run   Preview what would be imported

Examples:
  /ingest_consolidated
  /ingest_consolidated --source=/shared/dataCrystal
  /ingest_consolidated --dry-run
"""
