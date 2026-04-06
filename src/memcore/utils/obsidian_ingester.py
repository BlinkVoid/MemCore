"""
Obsidian Ingester - Improved vault ingestion with CLI support fallback.

Features:
- Frontmatter-aware parsing (YAML metadata)
- Obsidian-specific syntax support (#tags, [[links]], callouts)
- Batch processing for performance
- CLI integration (if available)
- Graceful fallback to file watching
- Link graph extraction
"""
import os
import re
import json
import yaml
import uuid
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
import asyncio


@dataclass
class ObsidianNote:
    """Represents a parsed Obsidian note."""
    path: str
    title: str
    content: str
    frontmatter: Dict[str, Any]
    tags: List[str]
    links: List[str]  # Internal [[links]]
    backlinks: List[str]  # Notes linking to this one
    created: Optional[str]
    modified: Optional[str]
    embedding_ready: bool = False


class ObsidianIngester:
    """
    Advanced Obsidian vault ingestion with multiple strategies.

    Strategy priority:
    1. Obsidian CLI (if available) - structured export
    2. File-based with frontmatter parsing
    3. Raw markdown with regex extraction
    """

    def __init__(
        self,
        vault_path: str,
        llm=None,
        vector_store=None,
        graph_store=None,
        use_cli: bool = True
    ):
        self.vault_path = Path(vault_path)
        self.llm = llm
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.use_cli = use_cli
        self._cli_available: Optional[bool] = None
        self._link_graph: Dict[str, Set[str]] = {}

    def _check_cli_available(self) -> bool:
        """Check if Obsidian CLI is installed and accessible."""
        if self._cli_available is not None:
            return self._cli_available

        try:
            # Try to run obsidian --version or similar
            result = subprocess.run(
                ["obsidian", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self._cli_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._cli_available = False

        return self._cli_available

    async def ingest_vault(
        self,
        force_rescan: bool = False,
        batch_size: int = 10,
        include_attachments: bool = False
    ) -> Dict[str, Any]:
        """
        Main ingestion entry point.

        Args:
            force_rescan: Re-process all files even if unchanged
            batch_size: Number of files to process in parallel
            include_attachments: Also index attachment metadata

        Returns:
            Ingestion statistics and results
        """
        if not self.vault_path.exists():
            return {"success": False, "error": f"Vault not found: {self.vault_path}"}

        start_time = datetime.now()

        # Try CLI first if enabled
        if self.use_cli and self._check_cli_available():
            return await self._ingest_via_cli()

        # Fall back to file-based ingestion
        return await self._ingest_via_files(force_rescan, batch_size)

    async def _ingest_via_cli(self) -> Dict[str, Any]:
        """
        Use Obsidian CLI for structured export.

        This would use commands like:
        - obsidian export --format=json
        - obsidian vault stats
        etc.
        """
        # Placeholder for CLI integration
        # Since actual CLI commands are unknown, we implement a fallback
        return await self._ingest_via_files(force_rescan=True, batch_size=20)

    async def _ingest_via_files(
        self,
        force_rescan: bool,
        batch_size: int
    ) -> Dict[str, Any]:
        """File-based ingestion with frontmatter support."""
        # First pass: build link graph
        await self._build_link_graph()

        # Second pass: process files (excluding deleted/ignored)
        all_md_files = list(self.vault_path.rglob("*.md"))

        # Filter out excluded files
        md_files = []
        excluded_count = 0
        for f in all_md_files:
            if self.graph_store and self.graph_store.is_obsidian_excluded(str(f)):
                excluded_count += 1
                continue
            md_files.append(f)

        stats = {
            "total_files": len(all_md_files),
            "excluded_files": excluded_count,
            "processed_files": len(md_files),
            "processed": 0,
            "failed": 0,
            "entries_created": 0,
            "tags_extracted": set(),
            "links_found": 0
        }

        # Process in batches
        for i in range(0, len(md_files), batch_size):
            batch = md_files[i:i + batch_size]
            tasks = [self._process_file(f, force_rescan) for f in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    stats["failed"] += 1
                else:
                    stats["processed"] += 1
                    stats["entries_created"] += result.get("entries", 0)
                    stats["tags_extracted"].update(result.get("tags", []))
                    stats["links_found"] += len(result.get("links", []))

        stats["tags_extracted"] = list(stats["tags_extracted"])
        stats["duration_sec"] = (datetime.now() - stats.get("start_time", datetime.now())).total_seconds()

        return {"success": True, "method": "file", "stats": stats}

    def _build_link_graph(self):
        """First pass: find all internal links."""
        self._link_graph = {}

        for md_file in self.vault_path.rglob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Find [[links]]
                links = set(re.findall(r'\[\[([^\]]+)\]\]', content))
                self._link_graph[str(md_file)] = links
            except Exception:
                pass

    async def _process_file(self, file_path: Path, force_rescan: bool) -> Dict[str, Any]:
        """Process a single markdown file."""
        try:
            note = self._parse_note(file_path)

            # Skip if unchanged and not forced
            if not force_rescan:
                # TODO: Check hash/timestamp
                pass

            # Build backlinks from link graph
            note.backlinks = [
                path for path, links in self._link_graph.items()
                if note.title in links or os.path.splitext(os.path.basename(path))[0] in links
            ]

            # Skip if no LLM (just return parsed data)
            if not self.llm:
                return {"entries": 0, "tags": note.tags, "links": note.links}

            # Generate embedding for full note
            note_content = self._prepare_note_content(note)

            # Create memory entry
            entries = await self._create_memory_entries(note, note_content)

            return {
                "entries": len(entries),
                "tags": note.tags,
                "links": note.links
            }

        except Exception as e:
            return {"error": str(e), "entries": 0, "tags": [], "links": []}

    def _parse_note(self, file_path: Path) -> ObsidianNote:
        """Parse a markdown file with frontmatter awareness."""
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        # Parse frontmatter
        frontmatter = {}
        content = raw_content

        if raw_content.startswith('---'):
            parts = raw_content.split('---', 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    content = parts[2].strip()
                except yaml.YAMLError:
                    pass

        # Extract tags from multiple sources
        tags = set()

        # 1. Frontmatter tags
        fm_tags = frontmatter.get('tags', [])
        if isinstance(fm_tags, str):
            fm_tags = [t.strip() for t in fm_tags.split(',')]
        tags.update(fm_tags)

        # 2. Inline #tags
        inline_tags = re.findall(r'#(\w+[-\w]*)', content)
        tags.update(inline_tags)

        # 3. Frontmatter aliases as pseudo-tags
        aliases = frontmatter.get('aliases', [])
        if isinstance(aliases, str):
            aliases = [aliases]

        # Extract internal links [[like this]]
        links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)

        # Get file timestamps
        stat = os.stat(file_path)
        created = datetime.fromtimestamp(stat.st_ctime).isoformat()
        modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

        return ObsidianNote(
            path=str(file_path),
            title=frontmatter.get('title', file_path.stem),
            content=content,
            frontmatter=frontmatter,
            tags=list(tags),
            links=links,
            backlinks=[],
            created=created,
            modified=modified
        )

    def _prepare_note_content(self, note: ObsidianNote) -> str:
        """Prepare note content for embedding."""
        # Include relevant frontmatter in content for better context
        sections = []

        if note.frontmatter.get('description'):
            sections.append(f"Description: {note.frontmatter['description']}")

        # Add tags context
        if note.tags:
            sections.append(f"Tags: {', '.join(note.tags)}")

        # Main content
        sections.append(note.content)

        # Add link context
        if note.links:
            sections.append(f"Linked to: {', '.join(note.links[:10])}")

        return "\n\n".join(sections)

    async def _create_memory_entries(
        self,
        note: ObsidianNote,
        content: str
    ) -> List[str]:
        """Create memory entries from a note."""
        if not self.llm or not self.vector_store:
            return []

        entries = []

        # Strategy: Split long notes by headers
        sections = self._split_by_headers(note.content)

        if len(sections) <= 1:
            # Single entry for short notes
            sections = [{"title": note.title, "content": content}]

        for section in sections:
            if not section.get("content", "").strip():
                continue

            # Generate embedding
            vector = await self.llm.get_embedding(section["content"])

            # Build payload - generate deterministic UUID from note path + section
            id_seed = f"{note.path}:{section.get('title', 'main')}"
            memory_id = str(uuid.uuid5(uuid.NAMESPACE_URL, id_seed))

            payload = {
                "summary": f"{note.title}: {section.get('title', 'Note')}",
                "content": section["content"][:4000],  # Limit size
                "type": "obsidian",
                "quadrants": self._determine_quadrants(note),
                "tags": note.tags[:20],  # Limit tags
                "importance": self._calculate_importance(note),
                "source_uri": f"obsidian://{note.path}",
                "obsidian_title": note.title,
                "obsidian_links": note.links[:10],
                "obsidian_backlinks": [os.path.basename(b) for b in note.backlinks[:5]],
                "created_at": note.created,
                "modified_at": note.modified,
                "ingested_at": datetime.now().isoformat()
            }

            # Store in vector DB
            self.vector_store.upsert_memory(memory_id, vector, payload)

            # Add to graph
            if self.graph_store:
                self.graph_store.add_node(
                    memory_id,
                    node_type="obsidian",
                    metadata=payload,
                    source_uri=payload.get("source_uri")
                )
                for link in note.links[:5]:
                    # Generate deterministic UUID for linked note
                    link_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.vault_path}/{link}.md:main"))
                    self.graph_store.add_edge(
                        memory_id,
                        link_id,
                        "LINKS_TO",
                        metadata={"context": "obsidian_link", "link_name": link}
                    )

            entries.append(memory_id)

        return entries

    def _split_by_headers(self, content: str) -> List[Dict[str, str]]:
        """Split content by markdown headers."""
        sections = []
        current_title = "Main"
        current_content = []

        for line in content.split('\n'):
            # Match ## headers
            header_match = re.match(r'^##+\s+(.+)$', line)

            if header_match:
                # Save previous section
                if current_content:
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
        if current_content:
            sections.append({
                "title": current_title,
                "content": '\n'.join(current_content).strip()
            })

        return sections

    def _determine_quadrants(self, note: ObsidianNote) -> List[str]:
        """Determine which quadrants this note belongs to."""
        quadrants = set()

        # Check frontmatter
        if 'quadrant' in note.frontmatter:
            q = note.frontmatter['quadrant']
            if isinstance(q, list):
                quadrants.update(q)
            else:
                quadrants.add(q)

        # Infer from tags
        tag_lower = [t.lower() for t in note.tags]
        quadrant_map = {
            'coding': ['code', 'dev', 'programming', 'python', 'js', 'development'],
            'research': ['research', 'study', 'learning', 'paper', 'article'],
            'personal': ['personal', 'journal', 'diary', 'life'],
            'ai_instructions': ['ai', 'prompt', 'instruction', 'template']
        }

        for quadrant, keywords in quadrant_map.items():
            if any(kw in tag_lower for kw in keywords):
                quadrants.add(quadrant)

        # Default
        if not quadrants:
            quadrants.add('general')

        return list(quadrants)

    def _calculate_importance(self, note: ObsidianNote) -> float:
        """Calculate importance score based on various factors."""
        score = 0.5  # Base

        # More links = higher importance (hub note)
        link_count = len(note.links) + len(note.backlinks)
        if link_count > 10:
            score += 0.2
        elif link_count > 5:
            score += 0.1

        # Has description in frontmatter = curated note
        if note.frontmatter.get('description'):
            score += 0.1

        # Recently modified
        if note.modified:
            try:
                modified = datetime.fromisoformat(note.modified)
                days_since = (datetime.now() - modified).days
                if days_since < 7:
                    score += 0.1
            except:
                pass

        return min(score, 1.0)

    async def delete_file_and_exclude(self, file_path: str) -> Dict[str, Any]:
        """
        Delete all memories from a file and add it to exclusion list.

        Args:
            file_path: Path to the Obsidian file

        Returns:
            Dict with deletion results
        """
        if not self.graph_store:
            return {"success": False, "error": "Graph store not available"}

        source_uri = f"obsidian://{file_path}"

        # Delete from vector store
        if self.vector_store:
            self.vector_store.delete_memories_by_source(source_uri)

        # Delete from graph store
        self.graph_store.delete_nodes_by_source(source_uri)

        # Add to exclusion list
        self.graph_store.add_obsidian_exclusion(file_path, reason="deleted_by_user")

        return {
            "success": True,
            "file_path": file_path,
            "action": "deleted_and_excluded"
        }

    def get_excluded_files(self) -> List[Dict[str, Any]]:
        """Get list of excluded files."""
        if not self.graph_store:
            return []
        return self.graph_store.get_obsidian_exclusions()

    def get_vault_stats(self) -> Dict[str, Any]:
        """Get statistics about the vault without ingesting."""
        if not self.vault_path.exists():
            return {"error": "Vault not found"}

        md_files = list(self.vault_path.rglob("*.md"))
        attachments = list(self.vault_path.rglob("*"))
        attachments = [f for f in attachments if f.suffix in ['.png', '.jpg', '.pdf', '.mp4']]

        # Sample some files for tag analysis
        all_tags = set()
        for f in md_files[:50]:  # Sample first 50
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                tags = re.findall(r'#(\w+[-\w]*)', content)
                all_tags.update(tags)
            except:
                pass

        return {
            "vault_path": str(self.vault_path),
            "markdown_files": len(md_files),
            "attachments": len(attachments),
            "unique_tags_sampled": len(all_tags),
            "cli_available": self._check_cli_available()
        }
