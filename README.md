# Setwise — question paper generator & answer grader

FastAPI + MySQL 8 + React. Uploads syllabus material, generates a question
paper with NLP, lets faculty edit and preview it, exports DOCX and PDF, keeps an
archive of past papers, and grades submitted answers by semantic similarity.

## Run the backend

```bash
cd backend
.\.venv\Scripts\Activate.ps1 //option
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('wordnet'); nltk.download('punkt')"

mysql -u root -p < schema-mysql.sql   # or let create_all() build the tables
cp .env.example .env          # edit DATABASE_URL and JWT_SECRET
python seed.py                # demo accounts + sample material
uvicorn app.main:app --reload # http://localhost:8000/docs
```

Demo logins: `faculty@college.edu / setwise123`, `student@college.edu / setwise123`

## Run the frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Vite proxies `/api` to `localhost:8000`, so no CORS fiddling in development.

## Flow

1. **Upload** — PDF/DOCX/TXT is parsed, cleaned, and keyphrase-extracted into topics.
2. **Configure** — sections, question type per section, count, marks, difficulty mix.
3. **Generate** — `nlp_engine.generate_questions` builds MCQ/fill by blanking key
   phrases (distractors from embedding neighbours, then WordNet), and short/long
   from templates seeded with extracted concepts. Supporting sentences become the
   model answer used later for grading.
4. **Edit** — inline edits autosave on blur; `↻` swaps a question for a fresh one.
5. **Preview & export** — DOCX via python-docx, PDF via ReportLab, plus an answer key.
6. **Archive** — every paper is queryable by title, subject and semester.
7. **Grading** — `POST /api/grading/submit` scores each answer as
   `0.65 × SBERT cosine + 0.35 × concept coverage`, scaled to the question's marks.
   Faculty can override any score — the model assists, it doesn't examine.

## MySQL notes

Requires **MySQL 8.0**. On 5.7 the `JSON` type is weaker and a unique index on
`users.email VARCHAR(255)` under utf8mb4 exceeds the 767-byte COMPACT limit —
shorten that column to `VARCHAR(191)` if you're stuck on 5.7.

`extracted_text`, `questions.text`, `answer_key` and `response_text` use
`Text().with_variant(LONGTEXT, "mysql")`. MySQL's `TEXT` caps at 65,535 bytes,
which a syllabus PDF's extracted text will exceed; without the variant you get
truncation or a data-too-long error on the first real upload. Confirm the DDL
before you trust it:

```bash
python -c "
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mysql
from app.models import Upload
print(CreateTable(Upload.__table__).compile(dialect=mysql.dialect()))
"
```

`extracted_text` should read `LONGTEXT`, not `TEXT`.

`schema-postgres.sql` is kept alongside `schema.sql` — the models run on either
backend, so switching back is a `DATABASE_URL` change and nothing else.

## Notes before you deploy

- Scanned PDFs need OCR first; the upload endpoint rejects files with too little
  readable text rather than silently generating nonsense.
- Swap `create_all()` for Alembic migrations once the schema stabilises.
- `Paper.title.ilike()` in the archive search compiles to `LOWER(x) LIKE LOWER(y)`
  on MySQL. It works, but MySQL's default collation is already case-insensitive,
  so the `LOWER()` calls block index use. Switch to `.like()` if the archive grows.
- The generator is extractive. If you later want more fluent phrasing, replace
  the template branch in `generate_questions` with a fine-tuned T5 or an LLM call —
  the function signature stays the same.
