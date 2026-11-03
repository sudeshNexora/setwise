-- Setwise — PostgreSQL schema.
-- SQLAlchemy create_all() builds this automatically; this file is here for
-- review, for DBA sign-off, and for seeding a database by hand.

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(120)  NOT NULL,
    email         VARCHAR(255)  NOT NULL UNIQUE,
    password_hash VARCHAR(255)  NOT NULL,
    role          VARCHAR(20)   NOT NULL DEFAULT 'faculty',
    department    VARCHAR(120),
    created_at    TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE TABLE uploads (
    id             SERIAL PRIMARY KEY,
    owner_id       INTEGER NOT NULL REFERENCES users(id),
    filename       VARCHAR(255) NOT NULL,
    stored_path    VARCHAR(500) NOT NULL,
    subject        VARCHAR(160) NOT NULL,
    unit           VARCHAR(160),
    extracted_text TEXT    NOT NULL DEFAULT '',
    topics         JSONB   NOT NULL DEFAULT '[]',
    word_count     INTEGER NOT NULL DEFAULT 0,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_uploads_owner ON uploads(owner_id);

CREATE TABLE papers (
    id                SERIAL PRIMARY KEY,
    creator_id        INTEGER NOT NULL REFERENCES users(id),
    title             VARCHAR(255) NOT NULL,
    institution       VARCHAR(255) NOT NULL DEFAULT '',
    subject           VARCHAR(160) NOT NULL,
    semester          VARCHAR(60),
    total_marks       INTEGER NOT NULL DEFAULT 50,
    duration_minutes  INTEGER NOT NULL DEFAULT 90,
    instructions      TEXT    NOT NULL DEFAULT '',
    status            VARCHAR(20) NOT NULL DEFAULT 'draft',
    source_upload_ids JSONB   NOT NULL DEFAULT '[]',
    docx_path         VARCHAR(500),
    pdf_path          VARCHAR(500),
    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_papers_lookup ON papers(subject, semester, status);

CREATE TABLE sections (
    id          SERIAL PRIMARY KEY,
    paper_id    INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    title       VARCHAR(160) NOT NULL,
    instruction VARCHAR(255) NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE questions (
    id             SERIAL PRIMARY KEY,
    section_id     INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    text           TEXT    NOT NULL,
    qtype          VARCHAR(20) NOT NULL DEFAULT 'short',
    options        JSONB   NOT NULL DEFAULT '[]',
    answer_key     TEXT    NOT NULL DEFAULT '',
    marks          INTEGER NOT NULL DEFAULT 2,
    difficulty     VARCHAR(12) NOT NULL DEFAULT 'medium',
    topic          VARCHAR(160),
    position       INTEGER NOT NULL DEFAULT 0,
    edited_by_user SMALLINT NOT NULL DEFAULT 0
);
CREATE INDEX idx_questions_section ON questions(section_id, position);

CREATE TABLE answer_scripts (
    id          SERIAL PRIMARY KEY,
    paper_id    INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES users(id),
    total_score REAL    NOT NULL DEFAULT 0,
    graded_at   TIMESTAMP,
    CONSTRAINT uq_script UNIQUE (paper_id, student_id)
);

CREATE TABLE answers (
    id               SERIAL PRIMARY KEY,
    script_id        INTEGER NOT NULL REFERENCES answer_scripts(id) ON DELETE CASCADE,
    question_id      INTEGER NOT NULL REFERENCES questions(id),
    response_text    TEXT NOT NULL DEFAULT '',
    score            REAL NOT NULL DEFAULT 0,
    similarity       REAL NOT NULL DEFAULT 0,
    keyword_coverage REAL NOT NULL DEFAULT 0,
    feedback         TEXT NOT NULL DEFAULT '',
    overridden       SMALLINT NOT NULL DEFAULT 0
);
