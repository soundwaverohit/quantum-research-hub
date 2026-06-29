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
