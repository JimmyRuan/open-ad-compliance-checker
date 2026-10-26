-- Provision store.  Applied by app/store.py on startup; idempotent.
--
-- One table.  Ingest replaces its contents wholesale, which is the simplest
-- thing that satisfies "re-runnable" at 464 rows.  At 300 regulations changing
-- weekly you would add a content hash per row and valid_from/valid_to so an
-- update re-embeds only what changed and you can still answer "which version
-- of the rule did you check this ad against?" -- see DECISIONS.md.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS provision (
  node_id       TEXT PRIMARY KEY,         -- 12-cfr-1026.24-d-2-iii
  citation      TEXT NOT NULL,            -- 12 CFR 1026.24(d)(2)(iii)
  section       TEXT NOT NULL,            -- 1026.24
  part          TEXT NOT NULL,            -- 1026          <- the gate predicate
  regulation    TEXT NOT NULL,            -- Regulation Z
  agency        TEXT NOT NULL,            -- CFPB
  heading       TEXT NOT NULL,
  path          TEXT[] NOT NULL,          -- {d,2,iii}
  depth         INT  NOT NULL,
  kind          TEXT NOT NULL,            -- obligation|prohibition|definition|scope|exemption
  own_text      TEXT NOT NULL,            -- shown to the reviewer
  context_text  TEXT NOT NULL,            -- indexed + embedded (leaf + ancestors + subtree)
  url           TEXT NOT NULL,
  as_of         DATE NOT NULL,
  -- Generated, not trigger-maintained: a generated column cannot drift from
  -- context_text, which is exactly the failure a trigger eventually has.
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', context_text)) STORED,
  embedding     vector(384)
);

CREATE INDEX IF NOT EXISTS provision_tsv  ON provision USING GIN (tsv);
CREATE INDEX IF NOT EXISTS provision_vec  ON provision
       USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
-- The gate filters on `part` inside the search rather than after it.
CREATE INDEX IF NOT EXISTS provision_part ON provision (part);
