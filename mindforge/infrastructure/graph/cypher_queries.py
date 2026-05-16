"""Named Cypher query constants for all graph operations.

All write queries use UNWIND batches to minimise driver round-trips.
Every query filters by ``kb_id`` to enforce knowledge-base isolation.

Import style::

    from mindforge.infrastructure.graph.cypher_queries import (
        MERGE_CONCEPT,
        RETRIEVE_CONCEPT_NEIGHBORHOOD,
        ...
    )
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Schema setup — constraints and indexes
# (Run once at startup via Neo4jContext.ensure_schema())
# ---------------------------------------------------------------------------

CREATE_CONSTRAINTS = """
CREATE CONSTRAINT lesson_id_kb_id_unique IF NOT EXISTS
FOR (l:Lesson) REQUIRE (l.id, l.kb_id) IS UNIQUE;

CREATE CONSTRAINT concept_key_kb_id_unique IF NOT EXISTS
FOR (c:Concept) REQUIRE (c.key, c.kb_id) IS UNIQUE;

CREATE CONSTRAINT kb_id_unique IF NOT EXISTS
FOR (kb:KnowledgeBase) REQUIRE kb.id IS UNIQUE;
"""

CREATE_FULLTEXT_INDEX = """
CREATE FULLTEXT INDEX chunk_fact_text IF NOT EXISTS
FOR (n:Chunk|Fact) ON EACH [n.text];
"""

CREATE_VECTOR_INDEX = """
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
FOR (n:Chunk) ON n.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: $dimensions,
  `vector.similarity_function`: 'cosine'
}};
"""

# ---------------------------------------------------------------------------
# Knowledge base and lesson MERGE
# ---------------------------------------------------------------------------

MERGE_KNOWLEDGE_BASE = """
MERGE (kb:KnowledgeBase {id: $kb_id})
ON CREATE SET kb.name = $name
RETURN kb
"""

MERGE_LESSON = """
MERGE (l:Lesson {id: $lesson_id, kb_id: $kb_id})
ON CREATE SET l.title = $title, l.created_at = $created_at
ON MATCH  SET l.title = $title, l.updated_at = $updated_at
WITH l
MATCH (kb:KnowledgeBase {id: $kb_id})
MERGE (l)-[:BELONGS_TO]->(kb)
RETURN l
"""

# ---------------------------------------------------------------------------
# Lesson revision lifecycle — cleanup before re-indexing
# ---------------------------------------------------------------------------

DELETE_LESSON_ENTITIES = """
MATCH (l:Lesson {id: $lesson_id, kb_id: $kb_id})
OPTIONAL MATCH (l)-[:HAS_FACT]->(f:Fact)
OPTIONAL MATCH (l)-[:HAS_CHUNK]->(ch:Chunk)
OPTIONAL MATCH (l)-[:ASSERTS_RELATION]->(ra:RelationAssertion)
DETACH DELETE f, ch, ra, l
"""

DELETE_ORPHANED_CONCEPTS = """
MATCH (c:Concept)-[:IN_KNOWLEDGE_BASE]->(kb:KnowledgeBase {id: $kb_id})
WHERE NOT EXISTS { MATCH ()-[:ASSERTS_CONCEPT]->(c) }
DETACH DELETE c
"""

# ---------------------------------------------------------------------------
# Concept MERGE (batch via UNWIND)
# ---------------------------------------------------------------------------

MERGE_CONCEPT = """
UNWIND $concepts AS c
MERGE (concept:Concept {key: c.key, kb_id: $kb_id})
ON CREATE SET
    concept.name              = c.name,
    concept.primary_definition = c.definition,
    concept.normalized_key    = c.normalized_key,
    concept.kb_id             = $kb_id
ON MATCH SET
    concept.name              = c.name,
    concept.primary_definition = c.definition,
    concept.normalized_key    = c.normalized_key
WITH concept
MATCH (kb:KnowledgeBase {id: $kb_id})
MERGE (concept)-[:IN_KNOWLEDGE_BASE]->(kb)
"""

CREATE_ASSERTS_CONCEPT = """
UNWIND $assertions AS a
MATCH (l:Lesson {id: $lesson_id, kb_id: $kb_id})
MATCH (c:Concept {key: a.key, kb_id: $kb_id})
MERGE (l)-[r:ASSERTS_CONCEPT]->(c)
ON CREATE SET r.definition  = a.definition,
              r.confidence  = a.confidence
ON MATCH  SET r.definition  = a.definition,
              r.confidence  = a.confidence
"""

# ---------------------------------------------------------------------------
# Fact MERGE (batch via UNWIND)
# ---------------------------------------------------------------------------

MERGE_FACT = """
UNWIND $facts AS f
MERGE (fact:Fact {id: f.id})
ON CREATE SET fact.text      = f.text,
              fact.lesson_id = $lesson_id,
              fact.kb_id     = $kb_id
WITH fact, f
MATCH (l:Lesson {id: $lesson_id, kb_id: $kb_id})
MERGE (l)-[:HAS_FACT]->(fact)
"""

# ---------------------------------------------------------------------------
# Chunk MERGE (batch via UNWIND)
# ---------------------------------------------------------------------------

MERGE_CHUNK = """
UNWIND $chunks AS ch
MERGE (chunk:Chunk {id: ch.id})
ON CREATE SET chunk.text      = ch.text,
              chunk.position  = ch.position,
              chunk.lesson_id = $lesson_id,
              chunk.kb_id     = $kb_id
ON MATCH  SET chunk.text      = ch.text,
              chunk.position  = ch.position
WITH chunk, ch
MATCH (l:Lesson {id: $lesson_id, kb_id: $kb_id})
MERGE (l)-[:HAS_CHUNK]->(chunk)
"""

SET_CHUNK_EMBEDDINGS = """
UNWIND $chunks AS ch
MATCH (chunk:Chunk {id: ch.id})
SET chunk.embedding = ch.embedding
"""

CREATE_CHUNK_MENTIONS_CONCEPT = """
UNWIND $mentions AS m
MATCH (chunk:Chunk {id: m.chunk_id})
MATCH (concept:Concept {key: m.concept_key, kb_id: $kb_id})
MERGE (chunk)-[:MENTIONS]->(concept)
"""

# ---------------------------------------------------------------------------
# Relation assertion MERGE (batch via UNWIND)
# ---------------------------------------------------------------------------

CREATE_ASSERTS_RELATION = """
UNWIND $relations AS r
MERGE (ra:RelationAssertion {id: r.id})
ON CREATE SET ra.source_key  = r.source_key,
              ra.target_key  = r.target_key,
              ra.label       = r.label,
              ra.description = r.description,
              ra.lesson_id   = $lesson_id,
              ra.kb_id       = $kb_id
ON MATCH  SET ra.label       = r.label,
              ra.description = r.description
WITH ra, r
MATCH (l:Lesson {id: $lesson_id, kb_id: $kb_id})
MERGE (l)-[:ASSERTS_RELATION]->(ra)
"""

# ---------------------------------------------------------------------------
# Derived projection — RELATES_TO edges
# Rebuilt from RelationAssertions after every lesson index/delete cycle.
# ---------------------------------------------------------------------------

REBUILD_RELATES_TO_EDGES = """
// Delete all existing derived RELATES_TO edges within this KB
MATCH (src:Concept)-[rel:RELATES_TO]->(tgt:Concept)
WHERE src.kb_id = $kb_id AND tgt.kb_id = $kb_id
DELETE rel;

// Rebuild from all RelationAssertions in this KB
MATCH (ra:RelationAssertion {kb_id: $kb_id})
MATCH (src:Concept {key: ra.source_key, kb_id: $kb_id})
MATCH (tgt:Concept {key: ra.target_key, kb_id: $kb_id})
WITH src, tgt, ra.label AS label,
     count(*) AS support_count,
     collect(ra.lesson_id) AS source_lessons
MERGE (src)-[r:RELATES_TO {label: label}]->(tgt)
SET r.support_count  = support_count,
    r.source_lessons = source_lessons
"""

# ---------------------------------------------------------------------------
# Retrieval — concept neighborhood (Graph RAG core query)
# ---------------------------------------------------------------------------

RETRIEVE_CONCEPT_NEIGHBORHOOD = """
MATCH (c:Concept {key: $concept_key})-[:IN_KNOWLEDGE_BASE]->(kb {id: $kb_id})
OPTIONAL MATCH (c)<-[ac:ASSERTS_CONCEPT]-(l:Lesson)
OPTIONAL MATCH (l)-[:HAS_FACT]->(f:Fact)
OPTIONAL MATCH (c)-[rel:RELATES_TO]-(neighbor:Concept)
  -[:IN_KNOWLEDGE_BASE]->(kb)
OPTIONAL MATCH (neighbor)<-[nac:ASSERTS_CONCEPT]-(nl:Lesson)
RETURN
    c.key                                                      AS concept_key,
    c.name                                                     AS concept_name,
    c.primary_definition                                       AS concept_definition,
    collect(DISTINCT f.text)                                   AS facts,
    collect(DISTINCT {
        key:        neighbor.key,
        name:       neighbor.name,
        definition: nac.definition,
        relation:   coalesce(rel.label, 'RELATES_TO')
    })                                                         AS neighbors
"""

# ---------------------------------------------------------------------------
# Retrieval — fallback full-text search
# ---------------------------------------------------------------------------

FULLTEXT_SEARCH = """
CALL db.index.fulltext.queryNodes('chunk_fact_text', $query)
YIELD node, score
WHERE node.kb_id = $kb_id
RETURN node.text AS text,
       node.lesson_id AS lesson_id,
       labels(node)[0] AS node_type,
       score
ORDER BY score DESC
LIMIT $top_k
"""

# ---------------------------------------------------------------------------
# Retrieval — concept key extraction helpers
# ---------------------------------------------------------------------------

GET_CONCEPTS = """
MATCH (c:Concept)-[:IN_KNOWLEDGE_BASE]->(kb:KnowledgeBase {id: $kb_id})
RETURN c.key AS key, c.name AS name, c.primary_definition AS description,
       c.normalized_key AS normalized_key
ORDER BY c.name
"""

GET_LESSON_CONCEPTS = """
MATCH (l:Lesson {id: $lesson_id, kb_id: $kb_id})-[:ASSERTS_CONCEPT]->(c:Concept)
RETURN c.key AS key, c.name AS name, c.primary_definition AS description
ORDER BY c.name
"""

GET_CONCEPT_EDGES = """
MATCH (a:Concept)-[r:RELATES_TO]->(b:Concept)
WHERE a.kb_id = $kb_id AND b.kb_id = $kb_id
RETURN a.key AS source, b.key AS target,
       coalesce(r.relation, 'related_to') AS relation
"""

# ---------------------------------------------------------------------------
# Weak concept detection — Quiz Question Selection query
# ---------------------------------------------------------------------------

FIND_WEAK_CONCEPTS = """
MATCH (c:Concept)-[:IN_KNOWLEDGE_BASE]->(kb:KnowledgeBase {id: $kb_id})
OPTIONAL MATCH (c)<-[r:REVIEWED]-(u:User {id: $user_id})
WITH c,
     coalesce(r.ease_factor, 2.5)           AS ease,
     coalesce(r.last_review, date('1970-01-01')) AS last_reviewed,
     count { (c)-[:RELATES_TO]-() }         AS degree
WHERE ease < 2.3 OR r IS NULL
RETURN
    c.key                  AS key,
    c.name                 AS name,
    c.primary_definition   AS definition,
    ease                   AS ease_factor,
    degree                 AS graph_degree,
    last_reviewed          AS last_reviewed
ORDER BY ease ASC, degree DESC
LIMIT $limit
"""
