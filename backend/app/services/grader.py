"""
Answer grading.

Score = w1 * semantic similarity (Sentence-BERT cosine)
      + w2 * keyword coverage (how many model-answer concepts appear)

MCQ / fill questions are matched exactly instead.
"""
from __future__ import annotations

import re

from app.services.nlp_engine import extract_topics, load_embedder

W_SIMILARITY = 0.65
W_COVERAGE = 0.35


def _normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def semantic_similarity(model_answer: str, student_answer: str) -> float:
    if not model_answer.strip() or not student_answer.strip():
        return 0.0
    embedder = load_embedder()
    if embedder:
        import numpy as np

        vecs = embedder.encode([model_answer, student_answer], normalize_embeddings=True)
        return float(np.clip(np.dot(vecs[0], vecs[1]), 0.0, 1.0))

    # fallback: token overlap (Jaccard)
    a = set(_normalise(model_answer).split())
    b = set(_normalise(student_answer).split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def keyword_coverage(model_answer: str, student_answer: str) -> tuple[float, list[str]]:
    concepts = extract_topics(model_answer, top_k=8)
    if not concepts:
        return 0.0, []
    student = _normalise(student_answer)
    missed = [c for c in concepts if _normalise(c) not in student]
    covered = len(concepts) - len(missed)
    return covered / len(concepts), missed


def grade_objective(answer_key: str, response: str) -> float:
    return 1.0 if _normalise(answer_key) == _normalise(response) else 0.0


def grade_answer(question, response_text: str) -> dict:
    """question: an app.models.Question instance."""
    if question.qtype in ("mcq", "fill"):
        correct = grade_objective(question.answer_key, response_text)
        return {
            "score": round(correct * question.marks, 2),
            "similarity": correct,
            "keyword_coverage": correct,
            "feedback": "Correct." if correct else f"Expected: {question.answer_key}",
        }

    similarity = semantic_similarity(question.answer_key, response_text)
    coverage, missed = keyword_coverage(question.answer_key, response_text)
    raw = W_SIMILARITY * similarity + W_COVERAGE * coverage

    # a very short answer to a long question can't earn full marks
    if question.qtype == "long" and len(response_text.split()) < 40:
        raw *= 0.75

    score = round(min(raw, 1.0) * question.marks, 2)

    if raw >= 0.8:
        feedback = "Covers the expected points well."
    elif raw >= 0.5:
        feedback = "On the right track but incomplete."
    else:
        feedback = "Key ideas from the material are missing."
    if missed:
        feedback += " Not addressed: " + ", ".join(missed[:4]) + "."

    return {
        "score": score,
        "similarity": round(similarity, 3),
        "keyword_coverage": round(coverage, 3),
        "feedback": feedback,
    }
