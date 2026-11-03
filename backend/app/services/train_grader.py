"""
Calibrate the grading formula against real, human-marked answers.

Setwise scores an answer as:
    raw = w_similarity * semantic_similarity + w_coverage * keyword_coverage
    score = raw * question_marks

The weights (0.65 / 0.35) are a guess. This script replaces the guess with
weights fit to a CSV of answers your faculty actually graded, using linear
regression: given similarity and coverage as inputs, learn the weights that
best reproduce the human score.

Usage
-----
1. Build training_data/graded_answers.csv (see the template this script
   writes if the file doesn't exist yet). Columns:
       model_answer, student_answer, max_marks, human_score
2. Run:
       python -m app.services.train_grader
3. It writes backend/app/services/grader_weights.json. grader.py loads this
   file automatically if present, and falls back to the 0.65/0.35 default
   if it's missing — so training is optional, not required to run the app.

This needs at least ~30-40 graded examples to be worth anything. Fewer than
that, the fit will overfit noise; keep the default weights instead.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from app.services.grader import keyword_coverage, semantic_similarity

DATA_PATH = Path(__file__).resolve().parents[3] / "training_data" / "graded_answers.csv"
WEIGHTS_PATH = Path(__file__).resolve().parent / "grader_weights.json"

TEMPLATE_ROWS = [
    {
        "model_answer": "A stack follows last in first out. Push adds to the top, pop removes from the top.",
        "student_answer": "Stack is LIFO, push adds an item on top and pop removes the top item.",
        "max_marks": "2",
        "human_score": "2",
    },
    {
        "model_answer": "A stack follows last in first out. Push adds to the top, pop removes from the top.",
        "student_answer": "It stores data in order.",
        "max_marks": "2",
        "human_score": "0.5",
    },
]


def _ensure_template() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DATA_PATH.exists():
        return
    with DATA_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["model_answer", "student_answer", "max_marks", "human_score"])
        writer.writeheader()
        writer.writerows(TEMPLATE_ROWS)
    print(f"No training data found. Wrote a starter template to {DATA_PATH}")
    print("Replace it with real graded answers, then run this script again.")


def _load_rows() -> list[dict]:
    with DATA_PATH.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def train() -> None:
    _ensure_template()
    rows = _load_rows()

    if len(rows) < 10:
        print(f"Only {len(rows)} labeled rows. Add more graded answers before training —")
        print("fewer than ~30 will overfit; the default weights are safer until then.")
        return

    import numpy as np
    from sklearn.linear_model import LinearRegression

    X, y = [], []
    for row in rows:
        model_answer = row["model_answer"]
        student_answer = row["student_answer"]
        max_marks = float(row["max_marks"])
        human_score = float(row["human_score"])

        sim = semantic_similarity(model_answer, student_answer)
        cov, _ = keyword_coverage(model_answer, student_answer)
        X.append([sim, cov])
        y.append(human_score / max_marks)   # normalise to 0..1 so marks scale doesn't skew the fit

    X, y = np.array(X), np.array(y)

    # positive=True: a similarity or coverage score should never PULL the mark down.
    reg = LinearRegression(positive=True, fit_intercept=False)
    reg.fit(X, y)

    w_sim, w_cov = reg.coef_
    total = w_sim + w_cov
    if total > 0:                # normalise so the two weights sum to 1, matching the original formula's shape
        w_sim, w_cov = w_sim / total, w_cov / total

    predictions = reg.predict(X)
    mae = float(np.mean(np.abs(predictions - y)))

    WEIGHTS_PATH.write_text(json.dumps({
        "w_similarity": round(float(w_sim), 4),
        "w_coverage": round(float(w_cov), 4),
        "trained_on_rows": len(rows),
        "mean_absolute_error": round(mae, 4),
    }, indent=2))

    print(f"Trained on {len(rows)} graded answers.")
    print(f"w_similarity = {w_sim:.3f}, w_coverage = {w_cov:.3f}")
    print(f"Mean absolute error on training data: {mae:.3f} (as a fraction of max marks)")
    print(f"Saved to {WEIGHTS_PATH}")


if __name__ == "__main__":
    train()
