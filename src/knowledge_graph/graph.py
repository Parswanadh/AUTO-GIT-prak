"""Knowledge Graph - SQLite-based knowledge storage"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Node:
    """Graph node representing a concept or entity"""
    node_id: str
    node_type: str  # problem, solution, pattern, error, technique
    data: Dict[str, Any]
    created_at: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Edge:
    """Graph edge representing a relationship"""
    edge_id: str
    source_id: str
    target_id: str
    relationship: str  # solves, causes, similar_to, depends_on
    weight: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeGraph:
    """
    SQLite-based knowledge graph for storing and retrieving patterns
    
    Features:
    - Node and edge storage
    - Pattern matching
    - Similarity search
    - Knowledge accumulation
    """
    
    def __init__(self, db_path: str = "data/knowledge/graph.db"):
        """Initialize knowledge graph with SQLite database"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"Knowledge graph initialized: {self.db_path}")
    
    def _init_database(self):
        """Create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Nodes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Create indexes separately
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_node_type ON nodes(node_type)
            """)
            
            # Edges table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    edge_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    metadata TEXT,
                    FOREIGN KEY (source_id) REFERENCES nodes(node_id),
                    FOREIGN KEY (target_id) REFERENCES nodes(node_id)
                )
            """)
            
            # Create indexes separately
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_source ON edges(source_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_target ON edges(target_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_relationship ON edges(relationship)
            """)
            
            # Patterns table (aggregated knowledge)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    pattern_id TEXT PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    occurrences INTEGER DEFAULT 1,
                    success_rate REAL DEFAULT 1.0,
                    data TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    UNIQUE(pattern_type, signature)
                )
            """)
            
            conn.commit()
            logger.info("Database tables initialized")
    
    def add_node(
        self,
        node_id: str,
        node_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Node:
        """
        Add a node to the graph
        
        Args:
            node_id: Unique node identifier
            node_type: Type of node (problem, solution, etc.)
            data: Node data
            metadata: Additional metadata
            
        Returns:
            Created Node object
        """
        node = Node(
            node_id=node_id,
            node_type=node_type,
            data=data,
            created_at=datetime.now().isoformat(),
            metadata=metadata
        )
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO nodes
                    (node_id, node_type, data, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    node.node_id,
                    node.node_type,
                    json.dumps(node.data),
                    node.created_at,
                    json.dumps(node.metadata) if node.metadata else None
                ))
                
                conn.commit()
                logger.debug(f"Added node: {node_id} ({node_type})")
                
        except Exception as e:
            logger.error(f"Failed to add node: {e}")
            raise
        
        return node
    
    def add_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        relationship: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Edge:
        """
        Add an edge to the graph
        
        Args:
            edge_id: Unique edge identifier
            source_id: Source node ID
            target_id: Target node ID
            relationship: Relationship type
            weight: Edge weight
            metadata: Additional metadata
            
        Returns:
            Created Edge object
        """
        edge = Edge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
            weight=weight,
            metadata=metadata
        )
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO edges
                    (edge_id, source_id, target_id, relationship, weight, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    edge.edge_id,
                    edge.source_id,
                    edge.target_id,
                    edge.relationship,
                    edge.weight,
                    json.dumps(edge.metadata) if edge.metadata else None
                ))
                
                conn.commit()
                logger.debug(f"Added edge: {source_id} --[{relationship}]--> {target_id}")
                
        except Exception as e:
            logger.error(f"Failed to add edge: {e}")
            raise
        
        return edge
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT node_id, node_type, data, created_at, metadata
                    FROM nodes
                    WHERE node_id = ?
                """, (node_id,))
                
                row = cursor.fetchone()
                
                if row:
                    return Node(
                        node_id=row[0],
                        node_type=row[1],
                        data=json.loads(row[2]),
                        created_at=row[3],
                        metadata=json.loads(row[4]) if row[4] else None
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get node: {e}")
            return None
    
    def find_nodes(
        self,
        node_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Node]:
        """
        Find nodes by type
        
        Args:
            node_type: Filter by node type (None for all)
            limit: Maximum results
            
        Returns:
            List of matching nodes
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if node_type:
                    cursor.execute("""
                        SELECT node_id, node_type, data, created_at, metadata
                        FROM nodes
                        WHERE node_type = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (node_type, limit))
                else:
                    cursor.execute("""
                        SELECT node_id, node_type, data, created_at, metadata
                        FROM nodes
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))
                
                nodes = []
                for row in cursor.fetchall():
                    nodes.append(Node(
                        node_id=row[0],
                        node_type=row[1],
                        data=json.loads(row[2]),
                        created_at=row[3],
                        metadata=json.loads(row[4]) if row[4] else None
                    ))
                
                return nodes
                
        except Exception as e:
            logger.error(f"Failed to find nodes: {e}")
            return []
    
    def find_related(
        self,
        node_id: str,
        relationship: Optional[str] = None,
        direction: str = "outgoing"
    ) -> List[Node]:
        """
        Find nodes related to a given node
        
        Args:
            node_id: Source node ID
            relationship: Filter by relationship type
            direction: "outgoing", "incoming", or "both"
            
        Returns:
            List of related nodes
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                nodes = []
                
                # Outgoing edges
                if direction in ["outgoing", "both"]:
                    query = """
                        SELECT n.node_id, n.node_type, n.data, n.created_at, n.metadata
                        FROM nodes n
                        JOIN edges e ON n.node_id = e.target_id
                        WHERE e.source_id = ?
                    """
                    params = [node_id]
                    
                    if relationship:
                        query += " AND e.relationship = ?"
                        params.append(relationship)
                    
                    cursor.execute(query, params)
                    
                    for row in cursor.fetchall():
                        nodes.append(Node(
                            node_id=row[0],
                            node_type=row[1],
                            data=json.loads(row[2]),
                            created_at=row[3],
                            metadata=json.loads(row[4]) if row[4] else None
                        ))
                
                # Incoming edges
                if direction in ["incoming", "both"]:
                    query = """
                        SELECT n.node_id, n.node_type, n.data, n.created_at, n.metadata
                        FROM nodes n
                        JOIN edges e ON n.node_id = e.source_id
                        WHERE e.target_id = ?
                    """
                    params = [node_id]
                    
                    if relationship:
                        query += " AND e.relationship = ?"
                        params.append(relationship)
                    
                    cursor.execute(query, params)
                    
                    for row in cursor.fetchall():
                        nodes.append(Node(
                            node_id=row[0],
                            node_type=row[1],
                            data=json.loads(row[2]),
                            created_at=row[3],
                            metadata=json.loads(row[4]) if row[4] else None
                        ))
                
                return nodes
                
        except Exception as e:
            logger.error(f"Failed to find related nodes: {e}")
            return []
    
    def record_pattern(
        self,
        pattern_type: str,
        signature: str,
        data: Dict[str, Any],
        success: bool = True
    ):
        """
        Record a pattern occurrence
        
        Args:
            pattern_type: Type of pattern
            signature: Unique pattern signature
            data: Pattern data
            success: Whether pattern was successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if pattern exists
                cursor.execute("""
                    SELECT pattern_id, occurrences, success_rate
                    FROM patterns
                    WHERE pattern_type = ? AND signature = ?
                """, (pattern_type, signature))
                
                row = cursor.fetchone()
                
                if row:
                    # Update existing pattern
                    pattern_id, occurrences, success_rate = row
                    new_occurrences = occurrences + 1
                    new_success_rate = (
                        (success_rate * occurrences + (1.0 if success else 0.0))
                        / new_occurrences
                    )
                    
                    cursor.execute("""
                        UPDATE patterns
                        SET occurrences = ?,
                            success_rate = ?,
                            data = ?,
                            last_seen = ?
                        WHERE pattern_id = ?
                    """, (
                        new_occurrences,
                        new_success_rate,
                        json.dumps(data),
                        datetime.now().isoformat(),
                        pattern_id
                    ))
                else:
                    # Insert new pattern
                    import uuid
                    pattern_id = str(uuid.uuid4())[:12]
                    
                    cursor.execute("""
                        INSERT INTO patterns
                        (pattern_id, pattern_type, signature, occurrences,
                         success_rate, data, last_seen)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        pattern_id,
                        pattern_type,
                        signature,
                        1,
                        1.0 if success else 0.0,
                        json.dumps(data),
                        datetime.now().isoformat()
                    ))
                
                conn.commit()
                logger.debug(f"Recorded pattern: {pattern_type}/{signature}")
                
        except Exception as e:
            logger.error(f"Failed to record pattern: {e}")
    
    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_occurrences: int = 1,
        min_success_rate: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Get patterns matching criteria
        
        Args:
            pattern_type: Filter by pattern type
            min_occurrences: Minimum occurrences
            min_success_rate: Minimum success rate
            
        Returns:
            List of pattern dicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT pattern_id, pattern_type, signature, occurrences,
                           success_rate, data, last_seen
                    FROM patterns
                    WHERE occurrences >= ? AND success_rate >= ?
                """
                params = [min_occurrences, min_success_rate]
                
                if pattern_type:
                    query += " AND pattern_type = ?"
                    params.append(pattern_type)
                
                query += " ORDER BY occurrences DESC, success_rate DESC"
                
                cursor.execute(query, params)
                
                patterns = []
                for row in cursor.fetchall():
                    patterns.append({
                        "pattern_id": row[0],
                        "pattern_type": row[1],
                        "signature": row[2],
                        "occurrences": row[3],
                        "success_rate": row[4],
                        "data": json.loads(row[5]),
                        "last_seen": row[6]
                    })
                
                return patterns
                
        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Node counts by type
                cursor.execute("""
                    SELECT node_type, COUNT(*)
                    FROM nodes
                    GROUP BY node_type
                """)
                node_counts = dict(cursor.fetchall())
                
                # Total edges
                cursor.execute("SELECT COUNT(*) FROM edges")
                edge_count = cursor.fetchone()[0]
                
                # Pattern counts
                cursor.execute("""
                    SELECT pattern_type, COUNT(*)
                    FROM patterns
                    GROUP BY pattern_type
                """)
                pattern_counts = dict(cursor.fetchall())
                
                return {
                    "total_nodes": sum(node_counts.values()),
                    "nodes_by_type": node_counts,
                    "total_edges": edge_count,
                    "total_patterns": sum(pattern_counts.values()),
                    "patterns_by_type": pattern_counts
                }
                
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
