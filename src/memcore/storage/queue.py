"""
Stateful Consolidation Queue - SQLite-backed job queue for memory consolidation.
Ensures consolidation jobs survive process restarts and can be retried.
"""
import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ConsolidationQueue:
    """
    SQLite-backed queue for memory consolidation jobs.
    
    Features:
    - Persistent across process restarts
    - Prevents duplicate processing
    - Retry mechanism for failed jobs
    - Job status tracking
    - Batch processing support
    """
    
    def __init__(self, db_path: str = "dataCrystal/consolidation_queue.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the queue database schema."""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Main jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS consolidation_jobs (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    memory_content TEXT NOT NULL,
                    memory_summary TEXT NOT NULL,
                    quadrants TEXT NOT NULL,  -- JSON array
                    source_uri TEXT,
                    importance REAL DEFAULT 0.5,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            
            # Index for efficient querying by status
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status 
                ON consolidation_jobs(status)
            """)
            
            # Index for memory_id to prevent duplicates
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_memory_id 
                ON consolidation_jobs(memory_id)
            """)
            
            # Index for created_at for FIFO ordering
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at 
                ON consolidation_jobs(created_at)
            """)
            
            # Job history/log table for auditing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES consolidation_jobs(id)
                )
            """)
            
            # System metadata for queue state
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS queue_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def enqueue(self, memory_id: str, content: str, summary: str, 
                quadrants: List[str], source_uri: Optional[str] = None,
                importance: float = 0.5, max_retries: int = 3) -> str:
        """
        Add a memory to the consolidation queue.
        
        Returns:
            Job ID (or existing job ID if memory_id already queued)
        """
        # Check if this memory is already in the queue (not completed/failed)
        existing = self._get_active_job_by_memory_id(memory_id)
        if existing:
            return existing["id"]
        
        job_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO consolidation_jobs 
                (id, memory_id, memory_content, memory_summary, quadrants, 
                 source_uri, importance, status, max_retries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, memory_id, content, summary, json.dumps(quadrants),
                source_uri, importance, JobStatus.PENDING, max_retries
            ))
            
            # Log the creation
            cursor.execute("""
                INSERT INTO job_history (job_id, status, message)
                VALUES (?, ?, ?)
            """, (job_id, JobStatus.PENDING, "Job created"))
            
            conn.commit()
        
        return job_id
    
    def enqueue_batch(self, memories: List[Dict[str, Any]]) -> List[str]:
        """
        Add multiple memories to the queue in a single transaction.
        
        Args:
            memories: List of dicts with keys: memory_id, content, summary, 
                     quadrants, source_uri, importance
        
        Returns:
            List of job IDs
        """
        job_ids = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for mem in memories:
                memory_id = mem["memory_id"]
                
                # Skip if already in queue
                cursor.execute("""
                    SELECT id FROM consolidation_jobs 
                    WHERE memory_id = ? AND status IN ('pending', 'processing', 'retrying')
                """, (memory_id,))
                if cursor.fetchone():
                    continue
                
                job_id = str(uuid.uuid4())
                job_ids.append(job_id)
                
                cursor.execute("""
                    INSERT INTO consolidation_jobs 
                    (id, memory_id, memory_content, memory_summary, quadrants, 
                     source_uri, importance, status, max_retries)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id, memory_id, mem["content"], mem["summary"],
                    json.dumps(mem.get("quadrants", ["general"])),
                    mem.get("source_uri"),
                    mem.get("importance", 0.5),
                    JobStatus.PENDING,
                    mem.get("max_retries", 3)
                ))
                
                cursor.execute("""
                    INSERT INTO job_history (job_id, status, message)
                    VALUES (?, ?, ?)
                """, (job_id, JobStatus.PENDING, "Job created (batch)"))
            
            conn.commit()
        
        return job_ids
    
    def dequeue(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get pending jobs for processing.
        Marks them as 'processing' to prevent duplicate processing.
        
        Returns:
            List of job dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get pending jobs, ordered by creation time (FIFO)
            cursor.execute("""
                SELECT * FROM consolidation_jobs 
                WHERE status IN ('pending', 'retrying')
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            jobs = []
            
            for row in rows:
                job = dict(row)
                job["quadrants"] = json.loads(job["quadrants"])
                jobs.append(job)
                
                # Mark as processing
                cursor.execute("""
                    UPDATE consolidation_jobs 
                    SET status = ?, updated_at = ?, processed_at = ?
                    WHERE id = ?
                """, (JobStatus.PROCESSING, datetime.now().isoformat(),
                      datetime.now().isoformat(), job["id"]))
                
                cursor.execute("""
                    INSERT INTO job_history (job_id, status, message)
                    VALUES (?, ?, ?)
                """, (job["id"], JobStatus.PROCESSING, "Job started processing"))
            
            conn.commit()
            
        return jobs
    
    def mark_completed(self, job_id: str, result: Optional[Dict] = None):
        """Mark a job as successfully completed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE consolidation_jobs 
                SET status = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
            """, (JobStatus.COMPLETED, datetime.now().isoformat(),
                  datetime.now().isoformat(), job_id))
            
            message = "Job completed successfully"
            if result:
                message += f": {json.dumps(result)}"
            
            cursor.execute("""
                INSERT INTO job_history (job_id, status, message)
                VALUES (?, ?, ?)
            """, (job_id, JobStatus.COMPLETED, message))
            
            conn.commit()
    
    def mark_failed(self, job_id: str, error_message: str):
        """
        Mark a job as failed.
        If retry count < max_retries, will be retried on next dequeue.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get current retry count
            cursor.execute("""
                SELECT retry_count, max_retries FROM consolidation_jobs WHERE id = ?
            """, (job_id,))
            row = cursor.fetchone()
            
            if row:
                retry_count, max_retries = row
                
                if retry_count < max_retries - 1:
                    # Can retry
                    new_status = JobStatus.RETRYING
                    new_retry_count = retry_count + 1
                else:
                    # Exhausted retries
                    new_status = JobStatus.FAILED
                    new_retry_count = retry_count
                
                cursor.execute("""
                    UPDATE consolidation_jobs 
                    SET status = ?, retry_count = ?, error_message = ?, updated_at = ?
                    WHERE id = ?
                """, (new_status, new_retry_count, error_message,
                      datetime.now().isoformat(), job_id))
                
                cursor.execute("""
                    INSERT INTO job_history (job_id, status, message)
                    VALUES (?, ?, ?)
                """, (job_id, new_status, f"Failed: {error_message[:200]}"))
            
            conn.commit()
    
    def reset_processing_jobs(self):
        """
        Reset 'processing' jobs back to 'pending'.
        Call this on startup to recover from crashes.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM consolidation_jobs WHERE status = ?
            """, (JobStatus.PROCESSING,))
            
            processing_ids = [row[0] for row in cursor.fetchall()]
            
            if processing_ids:
                placeholders = ','.join(['?' for _ in processing_ids])
                cursor.execute(f"""
                    UPDATE consolidation_jobs 
                    SET status = ?, updated_at = ?
                    WHERE id IN ({placeholders})
                """, (JobStatus.PENDING, datetime.now().isoformat()) + tuple(processing_ids))
                
                for job_id in processing_ids:
                    cursor.execute("""
                        INSERT INTO job_history (job_id, status, message)
                        VALUES (?, ?, ?)
                    """, (job_id, JobStatus.PENDING, "Reset to pending (crash recovery)"))
                
                conn.commit()
                return len(processing_ids)
            
            return 0
    
    def get_pending_count(self) -> int:
        """Get count of pending jobs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM consolidation_jobs 
                WHERE status IN ('pending', 'retrying')
            """)
            return cursor.fetchone()[0]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Count by status
            cursor.execute("""
                SELECT status, COUNT(*) FROM consolidation_jobs
                GROUP BY status
            """)
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Total jobs
            cursor.execute("SELECT COUNT(*) FROM consolidation_jobs")
            total = cursor.fetchone()[0]
            
            # Oldest pending job
            cursor.execute("""
                SELECT MIN(created_at) FROM consolidation_jobs
                WHERE status IN ('pending', 'retrying')
            """)
            oldest_pending = cursor.fetchone()[0]
            
            # Recent failures (last 24 hours)
            cursor.execute("""
                SELECT COUNT(*) FROM consolidation_jobs
                WHERE status = 'failed' AND updated_at > datetime('now', '-1 day')
            """)
            recent_failures = cursor.fetchone()[0]
            
        return {
            "total_jobs": total,
            "pending": status_counts.get(JobStatus.PENDING, 0),
            "processing": status_counts.get(JobStatus.PROCESSING, 0),
            "retrying": status_counts.get(JobStatus.RETRYING, 0),
            "completed": status_counts.get(JobStatus.COMPLETED, 0),
            "failed": status_counts.get(JobStatus.FAILED, 0),
            "oldest_pending": oldest_pending,
            "recent_failures_24h": recent_failures
        }
    
    def get_job_history(self, job_id: str) -> List[Dict[str, Any]]:
        """Get full history for a specific job."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM job_history WHERE job_id = ? ORDER BY timestamp ASC
            """, (job_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def retry_failed_jobs(self, max_age_hours: Optional[int] = None) -> int:
        """
        Reset failed jobs back to pending for retry.
        
        Args:
            max_age_hours: Only retry jobs failed within this many hours
        
        Returns:
            Number of jobs reset
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if max_age_hours:
                cursor.execute("""
                    SELECT id FROM consolidation_jobs
                    WHERE status = 'failed' AND updated_at > datetime('now', '-{} hours')
                """.format(max_age_hours))
            else:
                cursor.execute("""
                    SELECT id FROM consolidation_jobs WHERE status = 'failed'
                """)
            
            failed_ids = [row[0] for row in cursor.fetchall()]
            
            if failed_ids:
                placeholders = ','.join(['?' for _ in failed_ids])
                cursor.execute(f"""
                    UPDATE consolidation_jobs 
                    SET status = ?, retry_count = 0, error_message = NULL, updated_at = ?
                    WHERE id IN ({placeholders})
                """, (JobStatus.PENDING, datetime.now().isoformat()) + tuple(failed_ids))
                
                for job_id in failed_ids:
                    cursor.execute("""
                        INSERT INTO job_history (job_id, status, message)
                        VALUES (?, ?, ?)
                    """, (job_id, JobStatus.PENDING, "Manually reset for retry"))
                
                conn.commit()
                return len(failed_ids)
            
            return 0
    
    def cleanup_old_jobs(self, days: int = 30):
        """
        Remove completed/failed jobs older than specified days.
        
        Returns:
            Number of jobs removed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM consolidation_jobs
                WHERE status IN ('completed', 'failed')
                AND updated_at < datetime('now', '-{} days')
            """.format(days))
            
            deleted = cursor.rowcount
            conn.commit()
            return deleted
    
    def _get_active_job_by_memory_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Check if a memory is already in an active job."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM consolidation_jobs 
                WHERE memory_id = ? AND status IN ('pending', 'processing', 'retrying')
            """, (memory_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
