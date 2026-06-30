-- Quantum Research Hub — SQLite schema (ARCHITECTURE.md §8)
-- Safe to run repeatedly: every statement is IF NOT EXISTS.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS papers (
  arxiv_id           TEXT PRIMARY KEY,
  title              TEXT NOT NULL,
  authors_json       TEXT,
  abstract           TEXT,
  categories_json    TEXT,
  published_date     TEXT,
  updated_date       TEXT,
  pdf_url            TEXT,
  pdf_path           TEXT,
  parsed_text_path   TEXT,
  paper_card_path    TEXT,
  relevance_score    REAL DEFAULT 0,
  novelty_score      REAL DEFAULT 0,
  implementation_score REAL DEFAULT 0,
  recommended_action TEXT DEFAULT 'track',
  status             TEXT DEFAULT 'discovered',
  created_at         TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at         TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_chunks (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  arxiv_id      TEXT NOT NULL,
  section       TEXT,
  chunk_index   INTEGER,
  chunk_text    TEXT NOT NULL,
  token_estimate INTEGER,
  embedding_id  TEXT,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(arxiv_id) REFERENCES papers(arxiv_id)
);

CREATE TABLE IF NOT EXISTS ideas (
  id                   TEXT PRIMARY KEY,
  title                TEXT NOT NULL,
  hypothesis           TEXT NOT NULL,
  source_arxiv_ids_json TEXT,
  novelty_score        REAL DEFAULT 0,
  feasibility_score    REAL DEFAULT 0,
  expected_compute_cost TEXT,
  status               TEXT DEFAULT 'proposed',
  idea_card_path       TEXT,
  created_at           TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at           TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiments (
  id                   TEXT PRIMARY KEY,
  idea_id              TEXT,
  title                TEXT NOT NULL,
  hypothesis           TEXT,
  status               TEXT DEFAULT 'proposed',
  folder_path          TEXT,
  config_path          TEXT,
  result_path          TEXT,
  validator_notes_path TEXT,
  created_at           TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at           TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(idea_id) REFERENCES ideas(id)
);

CREATE TABLE IF NOT EXISTS experiment_runs (
  id            TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  status        TEXT DEFAULT 'created',
  started_at    TEXT,
  finished_at   TEXT,
  metrics_json  TEXT,
  logs_path     TEXT,
  error_message TEXT,
  FOREIGN KEY(experiment_id) REFERENCES experiments(id)
);

CREATE TABLE IF NOT EXISTS agent_events (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp        TEXT DEFAULT CURRENT_TIMESTAMP,
  agent_name       TEXT NOT NULL,
  action           TEXT NOT NULL,
  input_summary    TEXT,
  output_summary   TEXT,
  status           TEXT,
  cost_estimate_json TEXT,
  artifact_path    TEXT
);

CREATE TABLE IF NOT EXISTS budget_events (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp             TEXT DEFAULT CURRENT_TIMESTAMP,
  budget_profile        TEXT,
  event_type            TEXT,
  estimated_tokens      INTEGER,
  estimated_cost        REAL,
  local_runtime_seconds REAL,
  notes                 TEXT
);

-- =============================================================================
-- Synthesis Engine: concept graph
-- =============================================================================

CREATE TABLE IF NOT EXISTS concepts (
  name          TEXT PRIMARY KEY,
  concept_type  TEXT NOT NULL,        -- method | ansatz | problem | model | math_object | benchmark | field | hardware
  description   TEXT DEFAULT '',
  aliases_json  TEXT DEFAULT '[]',
  paper_count   INTEGER DEFAULT 0,
  source        TEXT DEFAULT 'seed',  -- seed (curated ontology) | mined (discovered)
  salience      REAL DEFAULT 0.0,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_concepts (
  arxiv_id      TEXT NOT NULL,
  concept_name  TEXT NOT NULL,
  score         REAL DEFAULT 0.0,     -- salience (normalized mention frequency)
  mention_count INTEGER DEFAULT 0,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (arxiv_id, concept_name),
  FOREIGN KEY(arxiv_id) REFERENCES papers(arxiv_id),
  FOREIGN KEY(concept_name) REFERENCES concepts(name)
);

CREATE TABLE IF NOT EXISTS concept_edges (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source        TEXT NOT NULL,
  target        TEXT NOT NULL,
  relation      TEXT NOT NULL,        -- improves_on | generalizes | applied_to | requires | enables | combines | compared_to | benchmarked_on | co_occurs
  weight        REAL DEFAULT 1.0,     -- accumulates with each new paper evidence
  evidence_count INTEGER DEFAULT 0,   -- number of relation_evidence rows backing this edge
  paper_ids_json TEXT DEFAULT '[]',
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source, target, relation)
);

-- The atomic supervised unit for the training dataset: one sentence of
-- textual evidence for one typed relation between two concepts, with offsets.
CREATE TABLE IF NOT EXISTS relation_evidence (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  arxiv_id      TEXT NOT NULL,
  source        TEXT NOT NULL,
  target        TEXT NOT NULL,
  relation      TEXT NOT NULL,
  evidence_text TEXT NOT NULL,
  char_start    INTEGER DEFAULT 0,
  char_end      INTEGER DEFAULT 0,
  section       TEXT DEFAULT 'abstract',
  confidence    REAL DEFAULT 0.0,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(arxiv_id, source, target, relation, char_start)
);

-- Normalized alias -> canonical concept (seed ontology + mined terms).
CREATE TABLE IF NOT EXISTS concept_aliases (
  alias         TEXT PRIMARY KEY,     -- lower-cased surface form
  concept_name  TEXT NOT NULL,
  source        TEXT DEFAULT 'seed',  -- seed | mined
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(concept_name) REFERENCES concepts(name)
);

-- Candidate terms discovered by the domain-general miner but not yet promoted
-- to canonical concepts. Lets the ontology grow from any corpus, with review.
CREATE TABLE IF NOT EXISTS mined_terms (
  term          TEXT PRIMARY KEY,     -- lower-cased surface form
  display       TEXT DEFAULT '',      -- best-cased display form
  acronym       TEXT DEFAULT '',      -- detected acronym, if any
  inferred_type TEXT DEFAULT '',      -- suffix-inferred concept_type
  frequency     INTEGER DEFAULT 0,    -- total mentions across corpus
  doc_frequency INTEGER DEFAULT 0,    -- number of papers mentioning it
  salience      REAL DEFAULT 0.0,
  promoted      INTEGER DEFAULT 0,    -- 1 once added to concepts
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_concepts_type       ON concepts(concept_type);
CREATE INDEX IF NOT EXISTS idx_concepts_count      ON concepts(paper_count DESC);
CREATE INDEX IF NOT EXISTS idx_paper_concepts_c    ON paper_concepts(concept_name);
CREATE INDEX IF NOT EXISTS idx_edges_source        ON concept_edges(source);
CREATE INDEX IF NOT EXISTS idx_edges_target        ON concept_edges(target);
CREATE INDEX IF NOT EXISTS idx_edges_relation      ON concept_edges(relation);
CREATE INDEX IF NOT EXISTS idx_evidence_pair       ON relation_evidence(source, target, relation);
CREATE INDEX IF NOT EXISTS idx_evidence_arxiv      ON relation_evidence(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_aliases_concept     ON concept_aliases(concept_name);
CREATE INDEX IF NOT EXISTS idx_mined_salience      ON mined_terms(salience DESC);

-- Helpful indexes for the dashboard and daily run.
CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published_date);
CREATE INDEX IF NOT EXISTS idx_papers_status    ON papers(status);
CREATE INDEX IF NOT EXISTS idx_chunks_arxiv     ON paper_chunks(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_ideas_status     ON ideas(status);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_runs_experiment  ON experiment_runs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_events_agent     ON agent_events(agent_name);
CREATE INDEX IF NOT EXISTS idx_events_time      ON agent_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_budget_time      ON budget_events(timestamp);
