from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, faculty_only
from app.models import Paper, Question, Section, Upload, User
from app.schemas import (GenerateIn, PaperOut, PaperSummary, QuestionCreate,
                         QuestionOut, QuestionUpdate)
from app.services import exporter
from app.services.nlp_engine import extract_topics, generate_questions

router = APIRouter(prefix="/api/papers", tags=["papers"])


def _recalc_total(paper: Paper) -> None:
    paper.total_marks = sum(q.marks for s in paper.sections for q in s.questions)


@router.post("/generate", response_model=PaperOut, status_code=201)
def generate_paper(payload: GenerateIn, db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    uploads = (db.query(Upload)
                 .filter(Upload.id.in_(payload.upload_ids), Upload.owner_id == user.id)
                 .all())
    if not uploads:
        raise HTTPException(400, "Select at least one uploaded file to generate from.")

    corpus = "\n".join(u.extracted_text for u in uploads)
    # Always recompute fresh from the current extractor — the stored
    # Upload.topics snapshot is from whenever the file was uploaded and can
    # be stale if the extraction logic has changed since. Recomputing here
    # costs one extra pass over the text but guarantees generation always
    # uses the latest topic-extraction rules, not whatever ran at upload time.
    topics = extract_topics(corpus)
    if not topics:
        topics = list(dict.fromkeys(t for u in uploads for t in (u.topics or [])))

    paper = Paper(
        creator_id=user.id,
        title=payload.title,
        institution=payload.institution,
        subject=payload.subject,
        semester=payload.semester,
        duration_minutes=payload.duration_minutes,
        instructions=payload.instructions,
        source_upload_ids=[u.id for u in uploads],
        total_marks=0,
    )
    db.add(paper)
    db.flush()

    for s_index, spec in enumerate(payload.sections):
        section = Section(
            paper_id=paper.id, title=spec.title,
            instruction=spec.instruction, position=s_index,
        )
        db.add(section)
        db.flush()

        generated = generate_questions(
            text=corpus, qtype=spec.qtype, count=spec.count,
            marks_each=spec.marks_each, topics=topics,
            difficulty_mix=payload.difficulty_mix,
        )
        if not generated:
            raise HTTPException(
                422,
                f"Couldn't build questions for '{spec.title}'. "
                "The material may be too short or too sparse for that question type.",
            )
        for q_index, g in enumerate(generated):
            db.add(Question(
                section_id=section.id, text=g.text, qtype=g.qtype,
                options=g.options, answer_key=g.answer_key, marks=g.marks,
                difficulty=g.difficulty, topic=g.topic, position=q_index,
            ))

    db.commit()
    db.refresh(paper)
    _recalc_total(paper)
    db.commit()
    db.refresh(paper)
    return paper


@router.get("", response_model=list[PaperSummary])
def list_papers(
    subject: str | None = Query(None),
    semester: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = db.query(Paper)
    if user.role == "student":
        query = query.filter(Paper.status == "published")
    else:
        query = query.filter(Paper.creator_id == user.id)
    if subject:
        query = query.filter(Paper.subject == subject)
    if semester:
        query = query.filter(Paper.semester == semester)
    if q:
        query = query.filter(Paper.title.ilike(f"%{q}%"))
    return query.order_by(Paper.created_at.desc()).all()


@router.get("/{paper_id}", response_model=PaperOut)
def get_paper(paper_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found.")
    if user.role == "student" and paper.status != "published":
        raise HTTPException(403, "This paper hasn't been published yet.")
    return paper


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def edit_question(
    question_id: int, payload: QuestionUpdate,
    db: Session = Depends(get_db), user: User = Depends(faculty_only),
):
    question = db.get(Question, question_id)
    if not question or question.section.paper.creator_id != user.id:
        raise HTTPException(404, "Question not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    question.edited_by_user = 1
    db.commit()
    paper = question.section.paper
    _recalc_total(paper)
    db.commit()
    db.refresh(question)
    return question


@router.post("/questions", response_model=QuestionOut, status_code=201)
def add_question(payload: QuestionCreate, db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    section = db.get(Section, payload.section_id)
    if not section or section.paper.creator_id != user.id:
        raise HTTPException(404, "Section not found.")
    question = Question(
        section_id=section.id, text=payload.text, qtype=payload.qtype,
        options=payload.options, answer_key=payload.answer_key,
        marks=payload.marks, difficulty=payload.difficulty,
        position=len(section.questions), edited_by_user=1,
    )
    db.add(question)
    db.commit()
    _recalc_total(section.paper)
    db.commit()
    db.refresh(question)
    return question


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    question = db.get(Question, question_id)
    if not question or question.section.paper.creator_id != user.id:
        raise HTTPException(404, "Question not found.")
    paper = question.section.paper
    db.delete(question)
    db.commit()
    _recalc_total(paper)
    db.commit()


@router.post("/questions/{question_id}/regenerate", response_model=QuestionOut)
def regenerate_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    question = db.get(Question, question_id)
    if not question or question.section.paper.creator_id != user.id:
        raise HTTPException(404, "Question not found.")
    paper = question.section.paper
    uploads = db.query(Upload).filter(Upload.id.in_(paper.source_upload_ids)).all()
    corpus = "\n".join(u.extracted_text for u in uploads)
    topics = list(dict.fromkeys(t for u in uploads for t in (u.topics or [])))

    replacements = generate_questions(corpus, question.qtype, 3, question.marks, topics)
    existing = {q.text for s in paper.sections for q in s.questions}
    fresh = next((r for r in replacements if r.text not in existing), None)
    if not fresh:
        raise HTTPException(422, "No fresh question available from this material. Try adding more notes.")

    question.text = fresh.text
    question.options = fresh.options
    question.answer_key = fresh.answer_key
    question.topic = fresh.topic
    question.difficulty = fresh.difficulty
    db.commit()
    db.refresh(question)
    return question


@router.post("/{paper_id}/publish", response_model=PaperOut)
def publish(paper_id: int, db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    paper = db.get(Paper, paper_id)
    if not paper or paper.creator_id != user.id:
        raise HTTPException(404, "Paper not found.")
    paper.status = "published"
    db.commit()
    db.refresh(paper)
    return paper


@router.get("/{paper_id}/export/{fmt}")
def export(fmt: str, paper_id: int, db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    paper = db.get(Paper, paper_id)
    if not paper or paper.creator_id != user.id:
        raise HTTPException(404, "Paper not found.")

    if fmt == "docx":
        path, media = exporter.to_docx(paper), (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        paper.docx_path = path
    elif fmt == "pdf":
        path, media = exporter.to_pdf(paper), "application/pdf"
        paper.pdf_path = path
    elif fmt == "key":
        path, media = exporter.answer_key_docx(paper), (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    else:
        raise HTTPException(400, "Format must be docx, pdf or key.")

    db.commit()
    return FileResponse(path, media_type=media, filename=Path(path).name)
