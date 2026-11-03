"""
Tests for the AI generation service.

They use a fake model, so they need no Gemini key, no network, no database and
no web framework:

    cd backend
    python -m unittest discover -s tests -v
"""
import json
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.ai_service import (  # noqa: E402
    AIConfig, AIConfigError, AIGenerationError, AIService, BLANK, PaperContext,
    SectionRequest, build_prompt, build_source_text, normalize_question,
    parse_json, sample_source,
)


class FakeModel:
    """Stands in for Gemini: returns queued replies and records every prompt."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)


def mcq(n, answer="B"):
    return {
        "question": f"Which statement about relational concept number {n} is correct?",
        "options": [f"A) wrong one {n}", f"B) right {n}", f"C) wrong two {n}", f"D) wrong three {n}"],
        "correctAnswer": answer, "difficulty": "easy", "topic": f"topic {n}", "marks": 99,
    }


def short(n):
    return {
        "question": f"Explain why concept number {n} matters in a relational database.",
        "correctAnswer": f"Concept {n} matters because it keeps data consistent. It also simplifies queries.",
        "difficulty": "medium", "topic": f"topic {n}",
    }


def service(*replies, **config):
    model = FakeModel(*replies)
    sleeps = []
    svc = AIService(AIConfig(api_key="x", **config), complete=model,
                    sleep=sleeps.append, rng=random.Random(1))
    return svc, model, sleeps


CTX = PaperContext(title="End Sem", subject="DBMS", semester="III", duration_minutes=90)
SOURCE = "A relation is a set of tuples. A key uniquely identifies a tuple. " * 20


class ParsingTests(unittest.TestCase):
    def test_plain_fenced_and_wrapped_json(self):
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(parse_json('Sure! Here it is: {"a": 1} Hope that helps'), {"a": 1})

    def test_garbage_and_empty_raise(self):
        with self.assertRaises(ValueError):
            parse_json("no json here")
        with self.assertRaises(ValueError):
            parse_json("   ")


class NormalizeTests(unittest.TestCase):
    spec = SectionRequest("A", "mcq", 1, 2)

    def norm(self, raw, spec=None):
        return normalize_question(raw, spec or self.spec, random.Random(0))

    def test_mcq_prefixes_stripped_and_answer_resolved_from_every_style(self):
        base = {"question": "Which key has no redundant attributes?",
                "options": ["A) super key", "B. candidate key", "(c) foreign key", "D: none here"]}
        for answer in ("candidate key", "B", "b", "B)", "(B)", "Option B", "B. candidate key", "B) candidate key"):
            q = self.norm({**base, "correctAnswer": answer})
            self.assertIsNotNone(q, answer)
            self.assertEqual(q.answer_key, "candidate key", answer)
            self.assertIn("candidate key", q.options)
            self.assertNotIn("A)", " ".join(q.options))

    def test_mcq_unresolvable_or_too_few_options_rejected(self):
        self.assertIsNone(self.norm({"question": "Which is right here?", "options": ["x", "y", "z", "w"],
                                     "correctAnswer": "something else entirely"}))
        self.assertIsNone(self.norm({"question": "Which is right here?", "options": ["only"],
                                     "correctAnswer": "only"}))

    def test_short_option_never_matches_inside_a_longer_word(self):
        opts = ["x", "y", "z", "w"]
        for answer in ("something else entirely", "why not", "xyz"):
            self.assertIsNone(self.norm({"question": "Which is right here?", "options": opts,
                                         "correctAnswer": answer}), answer)

    def test_longer_answer_that_contains_exactly_one_option_is_accepted(self):
        q = self.norm({"question": "Which key has no redundant attributes?",
                       "options": ["super key", "candidate key", "foreign key", "alternate"],
                       "correctAnswer": "The candidate key is the minimal one"})
        self.assertEqual(q.answer_key, "candidate key")

    def test_missing_answer_rejected(self):
        short_spec = SectionRequest("B", "short", 1, 2)
        self.assertIsNone(self.norm({"question": "Define a relation schema properly."}, short_spec))
        self.assertIsNone(self.norm({"question": "Define a relation schema properly.", "correctAnswer": "  "},
                                    short_spec))

    def test_marks_come_from_config_not_model(self):
        q = self.norm({**mcq(1)})
        self.assertEqual(q.marks, 2)

    def test_list_answer_becomes_numbered_points(self):
        long_spec = SectionRequest("C", "long", 1, 8)
        q = self.norm({"question": "Discuss the relational model in detail.",
                       "correctAnswer": ["First point here.", "Second point here."]}, long_spec)
        self.assertEqual(q.answer_key, "1) First point here. 2) Second point here.")

    def test_fill_blank_normalised_or_inserted(self):
        fill = SectionRequest("D", "fill", 1, 1)
        q = self.norm({"question": "A ____ uniquely identifies a tuple in a relation.",
                       "correctAnswer": "primary key."}, fill)
        self.assertIn(BLANK, q.text)
        self.assertEqual(q.answer_key, "primary key")
        q = self.norm({"question": "A primary key uniquely identifies a tuple.",
                       "correctAnswer": "primary key"}, fill)
        self.assertEqual(q.text, f"A {BLANK} uniquely identifies a tuple.")
        self.assertIsNone(self.norm({"question": "Nothing to blank out in this sentence.",
                                     "correctAnswer": "banana"}, fill))

    def test_bad_difficulty_defaults_to_medium(self):
        q = self.norm({**mcq(1), "difficulty": "impossible"})
        self.assertEqual(q.difficulty, "medium")


class GenerateTests(unittest.TestCase):
    def test_happy_path_with_fenced_json_and_two_sections_of_same_type(self):
        sections = [SectionRequest("Section A", "short", 2, 2),
                    SectionRequest("Section B", "short", 1, 5),
                    SectionRequest("Section C", "mcq", 2, 1)]
        reply = "```json\n" + json.dumps({"sections": [
            {"section": 1, "questions": [short(1), short(2)]},
            {"section": 2, "questions": [short(3)]},
            {"section": 3, "questions": [mcq(4), mcq(5)]},
        ]}) + "\n```"
        svc, model, _ = service(reply)
        result = svc.generate(CTX, sections, SOURCE, {"easy": 35, "medium": 45, "hard": 20})
        self.assertEqual([len(r) for r in result], [2, 1, 2])
        self.assertEqual({q.marks for q in result[0]}, {2})
        self.assertEqual({q.marks for q in result[1]}, {5})      # same type, different marks: kept apart
        self.assertEqual(len(model.prompts), 1)

    def test_retry_only_asks_for_missing_questions_and_never_repeats(self):
        sections = [SectionRequest("Section A", "short", 3, 2)]
        first = {"sections": [{"section": 1, "questions": [short(1)]}]}
        second = {"sections": [{"section": 1, "questions": [short(1), short(2), short(3)]}]}  # repeats #1
        svc, model, _ = service(first, second)
        result = svc.generate(CTX, sections, SOURCE)
        texts = [q.text for q in result[0]]
        self.assertEqual(len(texts), 3)
        self.assertEqual(len(set(texts)), 3)                       # the repeat was dropped
        self.assertIn("exactly 2 short question(s)", model.prompts[1])
        self.assertIn(short(1)["question"], model.prompts[1])       # first one is on the avoid-list

    def test_invalid_json_then_valid_retries_with_backoff(self):
        sections = [SectionRequest("A", "short", 1, 2)]
        good = {"sections": [{"section": 1, "questions": [short(1)]}]}
        svc, model, sleeps = service("this is not json", good)
        result = svc.generate(CTX, sections, SOURCE)
        self.assertEqual(len(result[0]), 1)
        self.assertEqual(sleeps, [2])

    def test_rate_limit_error_is_retried(self):
        class RateLimited(Exception):
            code = 429
        good = {"sections": [{"section": 1, "questions": [short(1)]}]}
        svc, model, _ = service(RateLimited("slow down"), good)
        self.assertEqual(len(svc.generate(CTX, [SectionRequest("A", "short", 1, 2)], SOURCE)[0]), 1)
        self.assertEqual(len(model.prompts), 2)

    def test_fatal_error_is_not_retried(self):
        class BadKey(Exception):
            code = 401
        svc, model, sleeps = service(BadKey("API key not valid"))
        with self.assertRaises(AIGenerationError) as ctx:
            svc.generate(CTX, [SectionRequest("A", "short", 1, 2)], SOURCE)
        self.assertIn("API key not valid", str(ctx.exception))
        self.assertEqual(len(model.prompts), 1)
        self.assertEqual(sleeps, [])

    def test_exhausted_attempts_raise_instead_of_padding_the_paper(self):
        sections = [SectionRequest("Section A", "short", 3, 2)]
        partial = {"sections": [{"section": 1, "questions": [short(1)]}]}
        svc, model, _ = service(partial, {"sections": []}, {"sections": []})
        with self.assertRaises(AIGenerationError) as ctx:
            svc.generate(CTX, sections, SOURCE)
        self.assertIn("'Section A' has 1 of 3", str(ctx.exception))
        self.assertEqual(len(model.prompts), 3)

    def test_questions_without_answers_never_reach_the_paper(self):
        no_answer = {"question": "Explain the relational model in some detail."}
        svc, _, _ = service({"sections": [{"section": 1, "questions": [no_answer, short(1)]}]})
        result = svc.generate(CTX, [SectionRequest("A", "short", 1, 2)], SOURCE)
        self.assertEqual(result[0][0].topic, "topic 1")

    def test_extra_questions_are_trimmed_to_the_requested_count(self):
        svc, _, _ = service({"sections": [{"section": 1, "questions": [short(i) for i in range(1, 6)]}]})
        self.assertEqual(len(svc.generate(CTX, [SectionRequest("A", "short", 2, 2)], SOURCE)[0]), 2)

    def test_same_question_in_two_sections_is_kept_once(self):
        sections = [SectionRequest("A", "short", 1, 2), SectionRequest("B", "short", 1, 2)]
        reply = {"sections": [{"section": 1, "questions": [short(1)]},
                              {"section": 2, "questions": [short(1)]}]}
        again = {"sections": [{"section": 2, "questions": [short(2)]}]}
        svc, _, _ = service(reply, again)
        result = svc.generate(CTX, sections, SOURCE)
        self.assertNotEqual(result[0][0].text, result[1][0].text)

    def test_missing_key_raises_config_error(self):
        svc = AIService(AIConfig(api_key=""))
        with self.assertRaises(AIConfigError):
            svc.generate(CTX, [SectionRequest("A", "short", 1, 2)], SOURCE)

    def test_empty_source_and_unknown_type_rejected(self):
        svc, _, _ = service()
        with self.assertRaises(AIGenerationError):
            svc.generate(CTX, [SectionRequest("A", "short", 1, 2)], "   ")
        with self.assertRaises(AIGenerationError):
            svc.generate(CTX, [SectionRequest("A", "essay", 1, 2)], SOURCE)

    def test_regenerate_one_avoids_existing_questions(self):
        svc, model, _ = service({"sections": [{"section": 1, "questions": [short(1), short(2)]}]})
        existing = [short(1)["question"]]
        question = svc.regenerate_one(CTX, "short", 2, SOURCE, existing, difficulty="hard")
        self.assertEqual(question.text, short(2)["question"])
        self.assertIn("100% hard", model.prompts[0])


class ModelUnavailableTests(unittest.TestCase):
    def test_404_explains_how_to_fix_it(self):
        class NotFound(Exception):
            code = 404
        svc, model, sleeps = service(NotFound("This model is no longer available to new users"),
                                     model="gemini-old-flash")
        with self.assertRaises(AIGenerationError) as caught:
            svc.generate(CTX, [SectionRequest("A", "short", 1, 2)], SOURCE)
        message = str(caught.exception)
        self.assertIn("no longer available", message)         # Google's own message is kept
        self.assertIn("gemini-old-flash", message)            # says which model was tried
        self.assertIn("GEMINI_MODEL", message)                # and what to change
        self.assertEqual(len(model.prompts), 1)               # not retried

    def test_bad_key_message_points_at_the_key(self):
        class Forbidden(Exception):
            code = 403
        svc, _, _ = service(Forbidden("denied"))
        with self.assertRaises(AIGenerationError) as caught:
            svc.generate(CTX, [SectionRequest("A", "short", 1, 2)], SOURCE)
        self.assertIn("GEMINI_API_KEY", str(caught.exception))


class GeminiRequestShapeTests(unittest.TestCase):
    """Checks what is actually sent to Google, using a stand-in for the SDK."""

    def setUp(self):
        import types as pytypes
        self.sent = {}
        sent = self.sent

        class Config:
            def __init__(self, **kwargs):
                sent["config"] = kwargs

        class Models:
            def generate_content(self, model, contents, config):
                sent["model"], sent["contents"] = model, contents
                return pytypes.SimpleNamespace(text='{"sections": []}')

        class Client:
            def __init__(self, api_key):
                sent["api_key"] = api_key
                self.models = Models()

        google = pytypes.ModuleType("google")
        genai = pytypes.ModuleType("google.genai")
        types_mod = pytypes.ModuleType("google.genai.types")
        genai.Client, types_mod.GenerateContentConfig = Client, Config
        genai.types, google.genai = types_mod, genai
        self._saved = {k: sys.modules.get(k) for k in ("google", "google.genai", "google.genai.types")}
        sys.modules.update({"google": google, "google.genai": genai, "google.genai.types": types_mod})

    def tearDown(self):
        for key, module in self._saved.items():
            if module is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = module

    def test_request_uses_configured_model_and_json_mode_with_no_sampling_overrides(self):
        from app.services.ai_service import _make_gemini_complete
        complete = _make_gemini_complete(AIConfig(api_key="secret", model="gemini-3.8-flash"))
        self.assertEqual(complete("hello"), '{"sections": []}')
        self.assertEqual(self.sent["model"], "gemini-3.8-flash")
        self.assertEqual(self.sent["api_key"], "secret")
        self.assertEqual(self.sent["contents"], "hello")
        self.assertEqual(self.sent["config"], {"response_mime_type": "application/json"})

    def test_default_model_is_the_current_one(self):
        self.assertEqual(AIConfig().model, "gemini-3.8-flash")

    def test_missing_key_is_reported_before_any_request(self):
        from app.services.ai_service import _make_gemini_complete
        with self.assertRaises(AIConfigError):
            _make_gemini_complete(AIConfig(api_key=""))
        self.assertNotIn("model", self.sent)


class PromptTests(unittest.TestCase):
    def test_prompt_contains_source_noise_warning_and_only_needed_sections(self):
        sections = [SectionRequest("Section A", "short", 3, 2, "Answer all."),
                    SectionRequest("Section B", "long", 2, 8)]
        prompt = build_prompt(CTX, sections, [0, 2], SOURCE, None, [])
        self.assertIn("<study_material>", prompt)
        self.assertIn("headers and footers", prompt)
        self.assertIn("names of authors", prompt)
        self.assertIn('Section 2 - "Section B": write exactly 2 long question(s)', prompt)
        self.assertNotIn('Section 1 - "Section A"', prompt)
        self.assertIn("numbered key points", prompt)

    def test_answer_length_scales_with_marks(self):
        low = build_prompt(CTX, [SectionRequest("S", "short", 1, 1)], [1], SOURCE, None, [])
        high = build_prompt(CTX, [SectionRequest("S", "short", 1, 3)], [1], SOURCE, None, [])
        self.assertIn("1 complete sentence)", low)
        self.assertIn("3 complete sentences)", high)
        eight = build_prompt(CTX, [SectionRequest("S", "long", 1, 8)], [1], SOURCE, None, [])
        self.assertIn("4 numbered key points", eight)


class SourceTests(unittest.TestCase):
    def test_short_text_untouched(self):
        self.assertEqual(sample_source("hello world", 1000), "hello world")

    def test_long_text_is_sampled_from_start_middle_and_end(self):
        words = [f"word{i}" for i in range(20000)]
        text = " ".join(words)
        out = sample_source(text, 6000)
        self.assertLessEqual(len(out), 6000 + 50)
        self.assertIn("word0", out)
        self.assertIn("word19999", out)
        regions = {int(n) // 2000 for n in re.findall(r"word(\d+)", out)}
        self.assertGreaterEqual(len(regions), 6)                    # spread across the whole text

    def test_each_upload_gets_a_share(self):
        out = build_source_text(["AAA " * 5000, "BBB " * 5000], 6000)
        self.assertIn("AAA", out)
        self.assertIn("BBB", out)


if __name__ == "__main__":
    unittest.main()
