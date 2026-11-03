"""
OPTIONAL: calibrate the grading formula against real, human-marked answers.

Answers are scored as   w_similarity * similarity + w_coverage * keyword_coverage.
The defaults (0.65 / 0.35) are a guess. If you have answers a teacher actually
marked, this fits the two weights to reproduce those marks (a linear regression).

1. Fill backend/training_data/graded_answers.csv with columns:
       model_answer, student_answer, max_marks, human_score
   (30+ rows; fewer would just fit noise, so the script refuses)
2. Run, from backend/:   python -m app.services.train_grader
3. It writes app/services/grader_weights.json, which grader.py loads on the next start.

Skipping this is fine - the app works with the default weights.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from app.services.grader import keyword_coverage, semantic_similarity

DATA_PATH = Path(__file__).resolve().parents[2] / "training_data" / "graded_answers.csv"
WEIGHTS_PATH = Path(__file__).resolve().parent / "grader_weights.json"
FIELDS = ["model_answer", "student_answer", "max_marks", "human_score"]
MIN_ROWS = 30


def train() -> None:
    if not DATA_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DATA_PATH.open("w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS).writeheader()
        print(f"Created an empty template at {DATA_PATH}. Add marked answers, then run this again.")
        return

    with DATA_PATH.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) < MIN_ROWS:
        print(f"Only {len(rows)} rows. Add at least {MIN_ROWS} marked answers - fewer would fit noise.")
        return

    import numpy as np
    from sklearn.linear_model import LinearRegression

    X, y = [], []
    for row in rows:
        sim = semantic_similarity(row["model_answer"], row["student_answer"])
        cov, _ = keyword_coverage(row["model_answer"], row["student_answer"])
        X.append([sim, cov])
        y.append(float(row["human_score"]) / float(row["max_marks"]))
    X, y = np.array(X), np.array(y)

    reg = LinearRegression(positive=True, fit_intercept=False).fit(X, y)
    w_sim, w_cov = reg.coef_
    total = w_sim + w_cov
    if total <= 0:
        print("The fit found no usable signal in this data; keeping the default weights.")
        return
    w_sim, w_cov = w_sim / total, w_cov / total
    mae = float(np.mean(np.abs(reg.predict(X) - y)))

    WEIGHTS_PATH.write_text(json.dumps({
        "w_similarity": round(float(w_sim), 4), "w_coverage": round(float(w_cov), 4),
        "trained_on_rows": len(rows), "mean_absolute_error": round(mae, 4),
    }, indent=2))
    print(f"Trained on {len(rows)} rows: w_similarity={w_sim:.3f}, w_coverage={w_cov:.3f}, MAE={mae:.3f}")
    print(f"Saved {WEIGHTS_PATH}. Restart the backend to use it.")


if __name__ == "__main__":
    train()
