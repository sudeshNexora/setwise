# Setwise — AI question paper generator and answer grader

Upload syllabus or study material, and an LLM (Google Gemini) writes the question
paper from it. Edit the questions, preview the paper, export it as DOCX or PDF, keep
an archive of past papers, and grade student answers.

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + React Router |
| Backend | Python, FastAPI, SQLAlchemy |
| Database | MySQL 8 |
| Question writing | Google Gemini (`google-genai`) |
| Reading uploads | pdfplumber, python-docx |
| Export | python-docx (DOCX), ReportLab (PDF) |

## How a paper is made

1. **Upload** — a PDF/DOCX/TXT is read and cleaned: repeating page headers and footers
   (even when the wording changes part-way through the file), page numbers, figure
   captions, cover-page credits and code listings are removed.
2. **Configure** — sections, question types (MCQ, short, long, fill-in-the-blank), how many,
   marks each, and the easy/medium/hard mix.
3. **Generate** — the cleaned material and your configuration go into one prompt, and
   Gemini returns the whole paper as JSON. The backend then checks it:
   - every section has the requested number of questions, and **marks always come from your
     configuration**, never from the model;
   - MCQs have clean options and a correct answer that matches one of them;
     fill-in-the-blank questions have a blank; every question has an answer;
   - duplicates are dropped;
   - if anything is missing or invalid, it retries up to 3 times **asking only for the
     missing questions** (and telling the model what is already on the paper). If it still
     can't complete the paper it returns an error. It never pads a paper with filler.
4. **Edit / Preview / Export** — unchanged from before. The ↻ button asks the model for one
   replacement question of the same type, marks and difficulty.
5. **Grade** — `POST /api/grading/submit`. MCQ and fill-in-the-blank are exact-match; written
   answers are scored by similarity to the model answer plus keyword coverage, and faculty can
   override any score.

## Setup

### 1. Database
```sql
CREATE DATABASE setwise CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'setwise'@'localhost' IDENTIFIED BY 'setwise';
GRANT ALL PRIVILEGES ON setwise.* TO 'setwise'@'localhost';
```
Tables are created automatically on first start (`schema.sql` is there for reference).

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then edit it (see below)
python seed.py                                         # demo accounts + sample material
uvicorn app.main:app --reload 

cd                       # http://localhost:8000/docs
```
In `.env` set at least `DATABASE_URL`, `JWT_SECRET` and **`GEMINI_API_KEY`**
(free key: https://aistudio.google.com/apikey). The key stays on the server and never
reaches the browser. Open `http://localhost:8000/api/health` — it must show
`"ai_configured": true`.

`GEMINI_MODEL` defaults to `gemini-3.8-flash`. Google retires and renames models regularly; if
generation fails with a 404 "model is no longer available", set this one value to a current
model from https://ai.google.dev/gemini-api/docs/models and restart the backend. The code
deliberately sends no temperature/top_p, because Google advises leaving those at their defaults
for Gemini 3 models.

### 3. Frontend
```bash
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```
Demo logins after `seed.py`: `faculty@college.edu` / `setwise123` and
`student@college.edu` / `setwise123`.

### Better grading (optional)
```bash
pip install -r requirements-optional.txt
```
Adds Sentence-BERT, which understands that two answers *mean* the same thing. Without it,
grading falls back to word overlap: it ranks answers sensibly (exact answer > good
paraphrase > half right > unrelated) but is harsh on correct answers written in different
words. It is a large install (PyTorch), which is why it is optional.

## Tests
```bash
cd backend
python -m unittest discover -s tests -v
```
45 tests, no API key, database or network needed. They cover the AI service with a fake
model (parsing, validation, retries, top-up requests, fatal errors, MCQ answer resolution,
prompt contents), the upload cleaning (both footer wordings, code lines, captions, cover
metadata), topic extraction and grading.

**What the tests do not cover:** a real Gemini call, and the FastAPI/MySQL layer. Those need
your key and your database, so the first real run is the actual integration test. If a
generation fails, the error message returned to the browser says why.

## Things to know

- **Privacy and cost.** Your study material is sent to Google to generate questions, and API
  calls may be billed or rate-limited depending on your plan. Check Google's current terms for
  how the free tier uses submitted content before uploading material that is confidential.
- **Waiting time.** A model call takes noticeably longer than the old instant template approach
  (it depends on the model and paper size); the button shows "Generating…" meanwhile. Veda AI's background queue and live progress were not ported
  because that needs frontend changes.
- **Long material.** About 24,000 characters go into each prompt (`AI_MAX_SOURCE_CHARS`). Longer
  uploads are sampled evenly from start to end, so a whole book is covered thinly. Upload the
  unit or chapter you are examining for better questions.
- **Scanned PDFs** (images of pages) have no text to read; the upload is rejected. Run OCR first.
- **Limits.** Up to 10 sections and 40 questions per section.
- **"Attempt any three".** The paper's total marks add up every question, including optional ones.
- Review every generated paper before using it. A model can still write a wrong answer key.

## Project layout
```
backend/app/services/
  ai_service.py   prompt, Gemini call, validation, retries   (the Veda AI logic)
  extractor.py    PDF/DOCX/TXT reading and cleaning
  topics.py       key terms for the upload chips and grading
  grader.py       answer scoring
  exporter.py     DOCX / PDF
  train_grader.py optional: fit grading weights to teacher-marked answers
backend/app/routers/   auth, uploads, papers, grading
backend/tests/
frontend/              React app (unchanged)
```
