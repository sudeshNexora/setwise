-- Setwise — MySQL 8.0 schema.
-- SQLAlchemy create_all() builds this automatically; this file is here for
-- review, for DBA sign-off, and for seeding a database by hand.
--
-- Note the LONGTEXT columns: MySQL's TEXT caps at 65,535 bytes, which a
-- syllabus PDF's extracted text will exceed.

CREATE DATABASE IF NOT EXISTS setwise
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE setwise;

CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'faculty',
    department    VARCHAR(120),
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;

CREATE TABLE uploads (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    owner_id       INT          NOT NULL,
    filename       VARCHAR(255) NOT NULL,
    stored_path    VARCHAR(500) NOT NULL,
    subject        VARCHAR(160) NOT NULL,
    unit           VARCHAR(160),
    extracted_text LONGTEXT     NOT NULL,
    topics         JSON         NOT NULL,
    word_count     INT          NOT NULL DEFAULT 0,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_uploads_owner (owner_id),
    CONSTRAINT fk_uploads_owner FOREIGN KEY (owner_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE papers (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    creator_id        INT          NOT NULL,
    title             VARCHAR(255) NOT NULL,
    institution       VARCHAR(255) NOT NULL DEFAULT '',
    subject           VARCHAR(160) NOT NULL,
    semester          VARCHAR(60),
    total_marks       INT          NOT NULL DEFAULT 50,
    duration_minutes  INT          NOT NULL DEFAULT 90,
    instructions      TEXT,
    status            VARCHAR(20)  NOT NULL DEFAULT 'draft',
    source_upload_ids JSON         NOT NULL,
    docx_path         VARCHAR(500),
    pdf_path          VARCHAR(500),
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_papers_lookup (subject, semester, status),
    KEY idx_papers_creator (creator_id),
    CONSTRAINT fk_papers_creator FOREIGN KEY (creator_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE sections (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    paper_id    INT          NOT NULL,
    title       VARCHAR(160) NOT NULL,
    instruction VARCHAR(255) NOT NULL DEFAULT '',
    position    INT          NOT NULL DEFAULT 0,
    KEY idx_sections_paper (paper_id, position),
    CONSTRAINT fk_sections_paper FOREIGN KEY (paper_id)
        REFERENCES papers(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE questions (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    section_id     INT          NOT NULL,
    text           LONGTEXT     NOT NULL,
    qtype          VARCHAR(20)  NOT NULL DEFAULT 'short',
    options        JSON         NOT NULL,
    answer_key     LONGTEXT,
    marks          INT          NOT NULL DEFAULT 2,
    difficulty     VARCHAR(12)  NOT NULL DEFAULT 'medium',
    topic          VARCHAR(160),
    position       INT          NOT NULL DEFAULT 0,
    edited_by_user TINYINT      NOT NULL DEFAULT 0,
    KEY idx_questions_section (section_id, position),
    CONSTRAINT fk_questions_section FOREIGN KEY (section_id)
        REFERENCES sections(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE answer_scripts (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    paper_id    INT   NOT NULL,
    student_id  INT   NOT NULL,
    total_score FLOAT NOT NULL DEFAULT 0,
    graded_at   DATETIME,
    UNIQUE KEY uq_script (paper_id, student_id),
    KEY idx_scripts_student (student_id),
    CONSTRAINT fk_scripts_paper FOREIGN KEY (paper_id)
        REFERENCES papers(id) ON DELETE CASCADE,
    CONSTRAINT fk_scripts_student FOREIGN KEY (student_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE answers (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    script_id        INT      NOT NULL,
    question_id      INT      NOT NULL,
    response_text    LONGTEXT,
    score            FLOAT    NOT NULL DEFAULT 0,
    similarity       FLOAT    NOT NULL DEFAULT 0,
    keyword_coverage FLOAT    NOT NULL DEFAULT 0,
    feedback         TEXT,
    overridden       TINYINT  NOT NULL DEFAULT 0,
    KEY idx_answers_script (script_id),
    CONSTRAINT fk_answers_script FOREIGN KEY (script_id)
        REFERENCES answer_scripts(id) ON DELETE CASCADE,
    CONSTRAINT fk_answers_question FOREIGN KEY (question_id) REFERENCES questions(id)
) ENGINE=InnoDB;

-- For MySQL 5.7, change users.email to VARCHAR(191): utf8mb4 VARCHAR(255)
-- needs 1020 bytes for a unique index, over 5.7's 767-byte COMPACT limit.
