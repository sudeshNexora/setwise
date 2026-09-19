from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, faculty_only
from app.models import Answer, AnswerScript, Paper, Question, User
from app.schemas import AnswerResult, ScriptResult, SubmitScriptIn
from app.services.grader import grade_answer

router = APIRouter(prefix="/api/grading", tags=["grading"])


@router.post("/submit", response_model=ScriptResult, status_code=201)
def submit_and_grade(payload: SubmitScriptIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    paper = db.get(Paper, payload.paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found.")

    script = (db.query(AnswerScript)
                .filter(AnswerScript.paper_id == paper.id, AnswerScript.student_id == user.id)
                .first())
    if script:
        db.delete(script)
        db.flush()

    script = AnswerScript(paper_id=paper.id, student_id=user.id)
    db.add(script)
    db.flush()

    results, total = [], 0.0
    for item in payload.answers:
        question = db.get(Question, item.question_id)
        if not question:
            continue
        outcome = grade_answer(question, item.response_text)
        db.add(Answer(
            script_id=script.id, question_id=question.id,
            response_text=item.response_text, score=outcome["score"],
            similarity=outcome["similarity"],
            keyword_coverage=outcome["keyword_coverage"],
            feedback=outcome["feedback"],
        ))
        total += outcome["score"]
        results.append(AnswerResult(
            question_id=question.id, score=outcome["score"], max_marks=question.marks,
            similarity=outcome["similarity"], keyword_coverage=outcome["keyword_coverage"],
            feedback=outcome["feedback"],
        ))

    script.total_score = round(total, 2)
    script.graded_at = datetime.utcnow()
    db.commit()

    return ScriptResult(
        script_id=script.id, total_score=script.total_score,
        total_marks=paper.total_marks, results=results,
    )


@router.patch("/answers/{answer_id}", response_model=AnswerResult)
def override_score(answer_id: int, score: float, db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    """Faculty can overrule the machine score — the model is an assistant, not the examiner."""
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(404, "Answer not found.")
    question = db.get(Question, answer.question_id)
    if score < 0 or score > question.marks:
        raise HTTPException(400, f"Score must be between 0 and {question.marks}.")

    answer.score = score
    answer.overridden = 1
    answer.script.total_score = round(sum(a.score for a in answer.script.answers), 2)
    db.commit()
    return AnswerResult(
        question_id=question.id, score=answer.score, max_marks=question.marks,
        similarity=answer.similarity, keyword_coverage=answer.keyword_coverage,
        feedback=answer.feedback + " (adjusted by faculty)",
    )
