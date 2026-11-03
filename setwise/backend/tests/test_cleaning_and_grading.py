"""
Tests for upload cleaning, topic extraction and answer grading.
No database, web framework or API key needed:

    cd backend
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.extractor import _strip_running_headers_footers, clean  # noqa: E402
from app.services.grader import grade_answer, grade_objective  # noqa: E402
from app.services.topics import extract_topics  # noqa: E402

BODIES = [
    "A relation schema R is made up of a relation name and a list of attributes.",
    "A key K of a relation schema is a super key with no redundant attributes.",
    "The degree of a relation is the number of attributes in its relation schema.",
    "A domain is a set of atomic values that are indivisible in the relational model.",
    "The entity integrity constraint states that no primary key value can be NULL.",
    "A foreign key references the primary key of another relation to keep data consistent.",
    "The SELECT operation chooses a subset of tuples that satisfy a given condition.",
    "The PROJECT operation selects certain columns from a relation and discards the rest.",
    "A candidate key is a minimal super key with no redundant attributes at all.",
    "NATURAL JOIN removes the duplicate attribute that an EQUIJOIN would otherwise keep.",
    "An entity set is mapped to a relation by making each attribute a column of the table.",
    "A weak entity set depends on an owner entity for its identification in the schema.",
]


def build_pages():
    """A PDF stitched from two sources: the footer wording changes halfway."""
    pages = []
    for i, body in enumerate(BODIES[:6], start=1):
        pages.append(f"Database Management Systems\n{body}\nLohith B and Santosh H ,  Dept of CSE,CEC {i}")
    for i, body in enumerate(BODIES[6:], start=1):
        pages.append(f"Database Management Systems\n{body}\nLohith B and Santosh, Asst Prof, Dept of CEC,CEC Page {i}")
    return pages


class CleaningTests(unittest.TestCase):
    def test_footers_with_two_different_wordings_are_both_removed(self):
        text = clean("\n".join(_strip_running_headers_footers(build_pages()))).lower()
        for leaked in ("lohith", "santosh", "dept of", "database management systems"):
            self.assertNotIn(leaked, text)
        self.assertIn("relation schema", text)            # real content survives

    def test_a_sentence_that_legitimately_repeats_is_kept(self):
        pages = build_pages()
        pages[8] = pages[8].replace(BODIES[8], BODIES[0])  # same body on two pages
        text = clean("\n".join(_strip_running_headers_footers(pages)))
        self.assertEqual(text.count(BODIES[0]), 2)

    def test_code_and_notebook_output_removed_but_prose_starting_with_import_kept(self):
        raw = (
            "Important concept: a tuple is an ordered list of values.\n"
            "forest = RandomForestClassifier(n_estimators=100)\n"
            "forest.fit(X_train, y_train)\n"
            "print(forest.score(X_test, y_test))\n"
            "In [12]: model.predict(X)\n"
            "Import statements are explained later in the chapter.\n"
        )
        out = clean(raw)
        self.assertIn("Important concept", out)
        for code in ("RandomForestClassifier", "forest.fit", "print(", "In [12]"):
            self.assertNotIn(code, out)

    def test_cover_page_metadata_figure_captions_and_page_numbers_removed(self):
        raw = (
            "Notes prepared by - (Name & Designation) : Mr.LOHIT B and Mr.SANTOSH\n"
            "Course code:18CS53\n"
            "Figure 3.1\nThe attributes and tuples of a relation STUDENT.\n"
            "Page 7 of 40\n"
            "A relation is a set of tuples.\n"
        )
        out = clean(raw)
        self.assertNotIn("SANTOSH", out)
        self.assertNotIn("18CS53", out)
        self.assertNotIn("Page 7 of 40", out)
        self.assertIn("A relation is a set of tuples.", out)

    def test_line_wrapped_sentences_are_joined(self):
        self.assertEqual(clean("A tuple is an ordered\nlist of values."), "A tuple is an ordered list of values.")


class TopicTests(unittest.TestCase):
    TEXT = " ".join(BODIES) * 2

    def test_real_terms_found_generic_words_excluded(self):
        topics = extract_topics(self.TEXT)
        self.assertIn("relation", topics)
        self.assertTrue(any("key" in t for t in topics))
        for generic in ("data", "model", "figure", "feature", "example"):
            self.assertNotIn(generic, topics)

    def test_singular_and_plural_collapse(self):
        topics = extract_topics("tuple tuples tuple tuples. " * 5)
        self.assertEqual(len([t for t in topics if t.startswith("tuple")]), 1)


def question(qtype, answer, marks=4):
    return SimpleNamespace(qtype=qtype, answer_key=answer, marks=marks)


class GradingTests(unittest.TestCase):
    MODEL = ("A primary key uniquely identifies each tuple in a relation. "
             "It cannot contain NULL values because every tuple must be identifiable.")

    def test_objective_questions_are_exact_match(self):
        self.assertEqual(grade_objective("candidate key", " Candidate  Key. "), 1.0)
        right = grade_answer(question("mcq", "candidate key", 1), "candidate key")
        wrong = grade_answer(question("mcq", "candidate key", 1), "foreign key")
        self.assertEqual((right["score"], wrong["score"]), (1.0, 0.0))
        self.assertIn("Expected: candidate key", wrong["feedback"])

    def test_good_answer_scores_much_higher_than_unrelated_answer(self):
        q = question("short", self.MODEL)
        good = grade_answer(q, "A primary key uniquely identifies each tuple and can never be NULL.")
        bad = grade_answer(q, "Bananas are yellow fruit that grow in warm climates.")
        self.assertGreater(good["score"], 2.0)
        self.assertLess(bad["score"], 0.5)

    def test_an_exact_copy_of_the_model_answer_gets_full_marks(self):
        self.assertEqual(grade_answer(question("short", self.MODEL, 4), self.MODEL)["score"], 4.0)

    def test_score_never_exceeds_the_marks(self):
        self.assertLessEqual(grade_answer(question("short", self.MODEL, 2), self.MODEL)["score"], 2.0)

    def test_short_answer_to_long_question_is_penalised(self):
        long_model = "1) " + self.MODEL
        q = question("long", long_model, 8)
        brief = grade_answer(q, self.MODEL)
        self.assertLess(brief["score"], 8.0)


if __name__ == "__main__":
    unittest.main()
