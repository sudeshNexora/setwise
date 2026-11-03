"""
Answer grading.

Score = w1 * semantic similarity (Sentence-BERT cosine)
      + w2 * keyword coverage (how many model-answer terms the student used)

MCQ / fill-in-the-blank questions are matched exactly instead.

Sentence-BERT is optional (pip install -r requirements-optional.txt). Without
it, similarity falls back to word overlap, which still works but is cruder.

w1 / w2 default to 0.65 / 0.35. If app/services/grader_weights.json exists
(written by `python -m app.services.train_grader` from real human-marked
answers) those learned weights are used instead.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.topics import content_words

_WEIGHTS_PATH = Path(__file__).resolve().parent / "grader_weights.json"
_DEFAULT_WEIGHTS = {"w_similarity": 0.65, "w_coverage": 0.35}
_embedder = None


def _load_weights() -> dict:
    if _WEIGHTS_PATH.exists():
        try:
            data = json.loads(_WEIGHTS_PATH.read_text())
            return {"w_similarity": float(data["w_similarity"]), "w_coverage": float(data["w_coverage"])}
        except (ValueError, KeyError, TypeError):
            pass
    return dict(_DEFAULT_WEIGHTS)


_WEIGHTS = _load_weights()
W_SIMILARITY = _WEIGHTS["w_similarity"]
W_COVERAGE = _WEIGHTS["w_coverage"]


def load_embedder():
    """Sentence-BERT model, loaded once; None if sentence-transformers isn't installed."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embedder = False
    return _embedder or None


def _normalise(s: str) -> str:
    # punctuation and runs of spaces must not decide a mark: " Candidate  Key. " == "candidate key"
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def semantic_similarity(model_answer: str, student_answer: str) -> float:
    if not model_answer.strip() or not student_answer.strip():
        return 0.0
    embedder = load_embedder()
    if embedder:
        import numpy as np

        vecs = embedder.encode([model_answer, student_answer], normalize_embeddings=True)
        return float(np.clip(np.dot(vecs[0], vecs[1]), 0.0, 1.0))

    # Fallback without Sentence-BERT: overlap of meaningful (stemmed) words.
    # Weighted towards how much of the MODEL answer the student covered, so a
    # correct answer that is shorter or longer than the model answer isn't
    # punished the way plain Jaccard overlap would punish it.
    a = set(content_words(model_answer))
    b = set(content_words(student_answer))
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return 0.7 * (overlap / len(a)) + 0.3 * (overlap / len(b))


def keyword_coverage(model_answer: str, student_answer: str) -> tuple[float, list[str]]:
    """Share of the model answer's key words the student also used, plus the ones missed."""
    terms = content_words(model_answer)
    if not terms:
        return 0.0, []
    student = set(content_words(student_answer))
    missed = [word for stem, word in terms.items() if stem not in student]
    return (len(terms) - len(missed)) / len(terms), missed


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
    if content_words(question.answer_key):
        coverage, missed = keyword_coverage(question.answer_key, response_text)
        raw = W_SIMILARITY * similarity + W_COVERAGE * coverage
    else:
        # nothing to check keywords against: grade on similarity alone rather
        # than capping every answer at the similarity weight
        missed, coverage, raw = [], 0.0, similarity

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
