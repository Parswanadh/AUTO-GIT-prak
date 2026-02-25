"""
Local File-Based Checkpointer (No Docker/Redis Required)
=========================================================

Persistent state management using local files.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint
from typing import Optional, Dict, Any, Iterator
from pathlib import Path
import pickle
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LocalFileCheckpointer(BaseCheckpointSaver):
    """
    File-based checkpointing for LangGraph workflows.
    
    Stores checkpoints as pickle files in a local directory.
    Survives restarts and provides state persistence without Docker/Redis.
    
    Args:
        checkpoint_dir: Directory to store checkpoint files (default: .cache/checkpoints)
        ttl_hours: Hours to keep checkpoints before cleanup (default: 24)
    """
    
    def __init__(
        self,
        checkpoint_dir: str = ".cache/checkpoints",
        ttl_hours: int = 24
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        
        logger.info(f"✅ Local checkpointer initialized at {self.checkpoint_dir}")
    
    def _get_checkpoint_path(self, thread_id: str, checkpoint_id: str = None) -> Path:
        """Get path for checkpoint file"""
        if checkpoint_id:
            return self.checkpoint_dir / f"{thread_id}_{checkpoint_id}.pkl"
        else:
            return self.checkpoint_dir / f"{thread_id}_latest.pkl"
    
    def _get_metadata_path(self, thread_id: str) -> Path:
        """Get path for metadata file"""
        return self.checkpoint_dir / f"{thread_id}_metadata.json"
    
    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Save a checkpoint to disk.
        
        Args:
            config: Configuration with thread_id
            checkpoint: Checkpoint object to save
            metadata: Checkpoint metadata
        """
        try:
            thread_id = config["configurable"]["thread_id"]
            checkpoint_id = checkpoint.get("id", "latest")
            
            # Save checkpoint (pickle for object serialization)
            checkpoint_path = self._get_checkpoint_path(thread_id, checkpoint_id)
            with open(checkpoint_path, 'wb') as f:
                pickle.dump(checkpoint, f)
            
            # Save metadata (JSON for readability)
            metadata_path = self._get_metadata_path(thread_id)
            metadata_with_timestamp = {
                **metadata,
                "saved_at": datetime.now().isoformat(),
                "checkpoint_id": checkpoint_id,
                "checkpoint_file": str(checkpoint_path)
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata_with_timestamp, f, indent=2)
            
            logger.debug(f"💾 Checkpoint saved: {checkpoint_path.name}")
        
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
    
    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """
        Load the latest checkpoint from disk.
        
        Args:
            config: Configuration with thread_id
            
        Returns:
            Checkpoint object if found, None otherwise
        """
        try:
            thread_id = config["configurable"]["thread_id"]
            
            # Try latest checkpoint first
            checkpoint_path = self._get_checkpoint_path(thread_id)
            
            if not checkpoint_path.exists():
                logger.debug(f"No checkpoint found for thread {thread_id}")
                return None
            
            with open(checkpoint_path, 'rb') as f:
                checkpoint = pickle.load(f)
            
            logger.debug(f"📂 Checkpoint loaded: {checkpoint_path.name}")
            return checkpoint
        
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return None
    
    async def aget(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Async version of get"""
        return self.get(config)
    
    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: Dict[str, Any]
    ) -> None:
        """Async version of put"""
        self.put(config, checkpoint, metadata)
    
    def get_tuple(self, config: Dict[str, Any]) -> Optional[tuple]:
        """Get checkpoint as tuple (checkpoint, metadata)"""
        try:
            checkpoint = self.get(config)
            if checkpoint is None:
                return None
            
            # Load metadata
            thread_id = config["configurable"]["thread_id"]
            metadata_path = self._get_metadata_path(thread_id)
            
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            
            return (checkpoint, metadata)
        except Exception as e:
            logger.warning(f"Failed to get checkpoint tuple: {e}")
            return None
    
    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[tuple]:
        """Async version of get_tuple"""
        return self.get_tuple(config)
    
    def list(self, config: Dict[str, Any]) -> Iterator[Checkpoint]:
        """
        List all checkpoints for a thread.
        
        Args:
            config: Configuration with thread_id
            
        Yields:
            Checkpoint objects
        """
        try:
            thread_id = config["configurable"]["thread_id"]
            
            # Find all checkpoint files for this thread
            pattern = f"{thread_id}_*.pkl"
            checkpoint_files = sorted(
                self.checkpoint_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True  # Most recent first
            )
            
            for checkpoint_path in checkpoint_files:
                try:
                    with open(checkpoint_path, 'rb') as f:
                        checkpoint = pickle.load(f)
                        yield checkpoint
                except Exception as e:
                    logger.warning(f"Failed to load checkpoint {checkpoint_path}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Failed to list checkpoints: {e}")
    
    def cleanup_old_checkpoints(self) -> int:
        """
        Remove checkpoints older than TTL.
        
        Returns:
            Number of checkpoints removed
        """
        removed = 0
        current_time = datetime.now().timestamp()
        ttl_seconds = self.ttl_hours * 3600
        
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.pkl"):
                file_age = current_time - checkpoint_file.stat().st_mtime
                
                if file_age > ttl_seconds:
                    checkpoint_file.unlink()
                    removed += 1
                    logger.debug(f"🗑️  Removed old checkpoint: {checkpoint_file.name}")
            
            if removed > 0:
                logger.info(f"🗑️  Cleaned up {removed} old checkpoints")
        
        except Exception as e:
            logger.warning(f"Checkpoint cleanup failed: {e}")
        
        return removed
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get checkpointer statistics.
        
        Returns:
            Dict with checkpoint stats
        """
        try:
            checkpoint_files = list(self.checkpoint_dir.glob("*.pkl"))
            total_size = sum(f.stat().st_size for f in checkpoint_files)
            
            # Get unique threads
            threads = set()
            for f in checkpoint_files:
                thread_id = f.stem.split("_")[0]
                threads.add(thread_id)
            
            return {
                "checkpoint_count": len(checkpoint_files),
                "thread_count": len(threads),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "checkpoint_dir": str(self.checkpoint_dir)
            }
        
        except Exception as e:
            logger.warning(f"Failed to get stats: {e}")
            return {}
