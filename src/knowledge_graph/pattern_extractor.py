"""
Pattern Extractor - Extract patterns from pipeline runs
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import time

from .graph import KnowledgeGraph, Entity, Relationship


class PatternExtractor:
    """
    Extracts patterns from pipeline runs and stores them in the knowledge graph.
    Learns from successful and failed runs to improve future performance.
    """
    
    def __init__(self, knowledge_graph: Optional[KnowledgeGraph] = None):
        self.kg = knowledge_graph or KnowledgeGraph()
    
    def extract_from_run(self, run_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Extract patterns from a pipeline run and add to knowledge graph.
        
        Args:
            run_data: Dictionary with run information
                - run_id: Unique run identifier
                - project_name: Name of the project
                - status: 'success' or 'failed'
                - files: List of generated files
                - errors: List of errors encountered
                - execution_time: Total execution time
                - model_used: Model that was used
                - stage: Pipeline stage
        
        Returns:
            Dictionary with added entity and relationship IDs
        """
        run_id = run_data.get('run_id', self._generate_id())
        project_name = run_data.get('project_name', 'unknown')
        status = run_data.get('status', 'unknown')
        
        added = {'entities': [], 'relationships': []}
        
        # Create project entity
        project_entity = Entity(
            entity_id=f"project_{self._hash_string(project_name)}",
            entity_type='project',
            name=project_name,
            properties={
                'description': run_data.get('description', ''),
                'category': run_data.get('category', 'general')
            },
            created_at=time.time()
        )
        self.kg.add_entity(project_entity)
        added['entities'].append(project_entity.entity_id)
        
        # Create run entity
        run_entity = Entity(
            entity_id=f"run_{run_id}",
            entity_type='run',
            name=f"Run {run_id}",
            properties={
                'status': status,
                'execution_time': run_data.get('execution_time', 0),
                'model_used': run_data.get('model_used', 'unknown'),
                'stage': run_data.get('stage', 'unknown'),
                'timestamp': datetime.now().isoformat()
            },
            created_at=time.time()
        )
        self.kg.add_entity(run_entity)
        added['entities'].append(run_entity.entity_id)
        
        # Link run to project
        run_rel = Relationship(
            rel_id=f"rel_{self._generate_id()}",
            source_id=project_entity.entity_id,
            target_id=run_entity.entity_id,
            rel_type='has_run',
            properties={'run_number': run_data.get('run_number', 1)},
            weight=1.0,
            created_at=time.time()
        )
        self.kg.add_relationship(run_rel)
        added['relationships'].append(run_rel.rel_id)
        
        # Extract file patterns
        if 'files' in run_data:
            for file_info in run_data['files']:
                file_entity = self._extract_file_pattern(file_info, run_entity.entity_id)
                if file_entity:
                    added['entities'].append(file_entity.entity_id)
        
        # Extract error patterns
        if 'errors' in run_data and status == 'failed':
            for error_info in run_data['errors']:
                error_entities = self._extract_error_pattern(error_info, run_entity.entity_id)
                added['entities'].extend(error_entities)
        
        # Extract solution patterns if successful
        if status == 'success' and 'solutions' in run_data:
            for solution_info in run_data['solutions']:
                solution_entity = self._extract_solution_pattern(
                    solution_info, run_entity.entity_id
                )
                if solution_entity:
                    added['entities'].append(solution_entity.entity_id)
        
        return added
    
    def _extract_file_pattern(self, file_info: Dict[str, Any], 
                             run_id: str) -> Optional[Entity]:
        """Extract pattern from file generation"""
        file_path = file_info.get('path', '')
        file_type = Path(file_path).suffix
        
        # Create file pattern entity
        pattern_id = f"pattern_file_{self._hash_string(file_type)}"
        pattern_entity = Entity(
            entity_id=pattern_id,
            entity_type='pattern',
            name=f"File Pattern: {file_type}",
            properties={
                'pattern_type': 'file_generation',
                'file_type': file_type,
                'typical_size': file_info.get('size', 0),
                'common_sections': file_info.get('sections', []),
                'success_rate': 1.0  # Updated incrementally
            },
            created_at=time.time()
        )
        self.kg.add_entity(pattern_entity)
        
        # Link to run
        rel = Relationship(
            rel_id=f"rel_{self._generate_id()}",
            source_id=run_id,
            target_id=pattern_id,
            rel_type='uses_pattern',
            properties={'file_path': file_path},
            weight=1.0,
            created_at=time.time()
        )
        self.kg.add_relationship(rel)
        
        return pattern_entity
    
    def _extract_error_pattern(self, error_info: Dict[str, Any], 
                               run_id: str) -> List[str]:
        """Extract pattern from error"""
        error_type = error_info.get('type', 'unknown')
        error_message = error_info.get('message', '')
        
        # Create error pattern entity
        pattern_id = f"pattern_error_{self._hash_string(error_type)}"
        pattern_entity = Entity(
            entity_id=pattern_id,
            entity_type='pattern',
            name=f"Error Pattern: {error_type}",
            properties={
                'pattern_type': 'error',
                'error_type': error_type,
                'common_messages': [error_message],
                'occurrence_count': 1,
                'severity': error_info.get('severity', 'medium')
            },
            created_at=time.time()
        )
        self.kg.add_entity(pattern_entity)
        
        # Link to run
        rel = Relationship(
            rel_id=f"rel_{self._generate_id()}",
            source_id=run_id,
            target_id=pattern_id,
            rel_type='encounters_error',
            properties={
                'stage': error_info.get('stage', 'unknown'),
                'recoverable': error_info.get('recoverable', False)
            },
            weight=1.0,
            created_at=time.time()
        )
        self.kg.add_relationship(rel)
        
        return [pattern_id]
    
    def _extract_solution_pattern(self, solution_info: Dict[str, Any], 
                                  run_id: str) -> Optional[Entity]:
        """Extract pattern from successful solution"""
        solution_type = solution_info.get('type', 'unknown')
        
        # Create solution pattern entity
        pattern_id = f"pattern_solution_{self._hash_string(solution_type)}"
        pattern_entity = Entity(
            entity_id=pattern_id,
            entity_type='pattern',
            name=f"Solution Pattern: {solution_type}",
            properties={
                'pattern_type': 'solution',
                'solution_type': solution_type,
                'approach': solution_info.get('approach', ''),
                'effectiveness': solution_info.get('effectiveness', 1.0),
                'use_count': 1
            },
            created_at=time.time()
        )
        self.kg.add_entity(pattern_entity)
        
        # Link to run
        rel = Relationship(
            rel_id=f"rel_{self._generate_id()}",
            source_id=run_id,
            target_id=pattern_id,
            rel_type='applies_solution',
            properties={
                'context': solution_info.get('context', ''),
                'result': 'success'
            },
            weight=solution_info.get('effectiveness', 1.0),
            created_at=time.time()
        )
        self.kg.add_relationship(rel)
        
        return pattern_entity
    
    def find_similar_projects(self, project_name: str, limit: int = 5) -> List[Entity]:
        """Find similar projects based on patterns"""
        # Get project entity
        project_id = f"project_{self._hash_string(project_name)}"
        project = self.kg.get_entity(project_id)
        
        if not project:
            return []
        
        # Get runs for this project
        runs = self.kg.get_neighbors(project_id, rel_type='has_run')
        
        # Get patterns used in these runs
        pattern_ids = set()
        for run in runs:
            patterns = self.kg.get_neighbors(run.entity_id, rel_type='uses_pattern')
            pattern_ids.update(p.entity_id for p in patterns)
        
        # Find other projects using similar patterns
        similar_projects = []
        for pattern_id in pattern_ids:
            # Get runs using this pattern
            rels = self.kg.get_relationships(target_id=pattern_id, rel_type='uses_pattern')
            for rel in rels:
                # Get project for this run
                run = self.kg.get_entity(rel.source_id)
                if run:
                    project_rels = self.kg.get_relationships(
                        target_id=run.entity_id, 
                        rel_type='has_run'
                    )
                    for proj_rel in project_rels:
                        proj = self.kg.get_entity(proj_rel.source_id)
                        if proj and proj.entity_id != project_id:
                            similar_projects.append(proj)
        
        # Deduplicate and limit
        seen = set()
        unique_projects = []
        for proj in similar_projects:
            if proj.entity_id not in seen:
                seen.add(proj.entity_id)
                unique_projects.append(proj)
                if len(unique_projects) >= limit:
                    break
        
        return unique_projects
    
    def get_success_patterns(self, limit: int = 10) -> List[Entity]:
        """Get most successful patterns"""
        patterns = self.kg.find_entities(entity_type='pattern', limit=limit * 2)
        
        # Filter for patterns with high effectiveness
        successful = []
        for pattern in patterns:
            if pattern.properties.get('pattern_type') == 'solution':
                effectiveness = pattern.properties.get('effectiveness', 0)
                if effectiveness > 0.7:
                    successful.append(pattern)
        
        return successful[:limit]
    
    def _generate_id(self) -> str:
        """Generate unique ID"""
        return hashlib.md5(f"{time.time()}".encode()).hexdigest()[:12]
    
    def _hash_string(self, s: str) -> str:
        """Generate hash from string"""
        return hashlib.md5(s.encode()).hexdigest()[:12]
