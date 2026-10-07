"""
Question generation pipeline.

    text -> sentences -> candidate concept sentences -> questions

Heavy models (spaCy, sentence-transformers) are loaded lazily and each has a
lightweight fallback, so the API still runs on a machine where they are absent.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from sklearn.feature_extraction.text import TfidfVectorizer

_nlp = None
_embedder = None

STOP_START = ("the", "a", "an", "this", "these", "those", "it", "they")

# Single words that are too generic to make a real exam question on their own —
# "data", "model", "figure" pass every grammatical check (they're real nouns)
# but say nothing about what was actually taught. They're still fine INSIDE a
# multi-word term ("training data", "decision tree model"), so this only
# blocks them as a standalone, one-word topic.
GENERIC_UNIGRAMS = {
    "data", "model", "models", "figure", "figures", "table", "tables",
    "example", "examples", "method", "methods", "approach", "approaches",
    "system", "systems", "process", "processes", "type", "types", "case",
    "cases", "feature", "features", "information", "result", "results",
    "way", "ways", "number", "form", "forms", "aspect", "aspects", "part",
    "parts", "point", "points", "value", "values", "item", "items",
    "concept", "concepts", "unit", "units", "chapter", "chapters",
}

SHORT_TEMPLATES = [
    "Define {concept} and state where it is used.",
    "Explain the role of {concept} in the context of {topic}.",
    "List the key characteristics of {concept}.",
    "Differentiate {concept} from closely related approaches.",
    "Why is {concept} important in {topic}?",
]

LONG_TEMPLATES = [
    "Explain {concept} in detail with a suitable example and a diagram where applicable.",
    "Discuss the working of {concept}, and analyse its advantages and limitations.",
    "With reference to {topic}, describe {concept} and justify when it should be preferred.",
    "Compare {concept} with the alternatives discussed in {topic}, supporting your answer with reasoning.",
]


def _load_spacy():
    global _nlp
    if _nlp is None:
        try:
            import spacy

            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = False          # sentinel: unavailable
    return _nlp or None


def load_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embedder = False
    return _embedder or None


# ---------------------------------------------------------------- sentences
# Source material — especially programming-heavy textbooks — mixes real
# prose with Python code, Jupyter In[]/Out[] console output, and "see
# chapter N" cross-references. None of those are usable as a question or
# an answer even though they parse as grammatically valid "sentences".
_CODE_MARKERS = re.compile(
    r"(In|Out)\s*\[\s*\d*\s*\]\s*:"
    r"|\.fit\(|\.score\(|\.plot\(|\.predict\(|\.transform\("
    r"|print\(|import \w+|plt\.\w+\(|np\.\w+\("
    r"|\{:\.\d+f\}"
)
_CHAPTER_REF = re.compile(
    r"(?i)\b(in (the )?(next|previous|following) chapter"
    r"|see chapter\s*\d+|chapter\s*\d+\s+(covers|discusses|introduces))"
)


def _code_symbol_ratio(s: str) -> float:
    if not s:
        return 0.0
    symbols = sum(1 for c in s if c in "={}[]()<>_%")
    return symbols / len(s)


def _looks_like_code_or_noise(sentence: str) -> bool:
    """True for Python code, console output, or navigational cross-references
    that slipped through PDF extraction looking like ordinary sentences."""
    if _CODE_MARKERS.search(sentence):
        return True
    if _code_symbol_ratio(sentence) > 0.06:       # plain prose rarely exceeds ~2-3%
        return True
    if _CHAPTER_REF.search(sentence):
        return True
    if len(re.findall(r"[A-Za-z]{2,}", sentence)) < 6:   # too few real words to be content
        return True
    return False


def split_sentences(text: str) -> list[str]:
    nlp = _load_spacy()
    if nlp:
        doc = nlp(text[:900_000])
        sents = [s.text.strip() for s in doc.sents]
    else:
        sents = re.split(r"(?<=[.!?])\s+", text)
    return [
        s.strip() for s in sents
        if 40 <= len(s.strip()) <= 320 and not _looks_like_code_or_noise(s)
    ]


# ----------------------------------------------------------------- concepts
# Words that make a "topic" unusable as the object of a sentence —
# pronouns, ordinals, vague quantifiers picked up by noun-chunking.
_JUNK_HEADS = {
    "it", "they", "he", "she", "this", "that", "these", "those", "which",
    "who", "what", "one", "some", "any", "each", "every", "following",
    "example", "way", "case", "time", "number", "type", "kind",
}


def _strip_leading_determiners(tokens):
    """Drop leading articles/pronouns/possessives so the phrase starts on its head noun."""
    while tokens and tokens[0].lower() in STOP_START or (tokens and tokens[0].lower() in {
        "its", "their", "our", "your", "his", "her", "such", "other",
    }):
        tokens = tokens[1:]
    return tokens


def extract_topics(text: str, top_k: int = 12) -> list[str]:
    """Keyphrases that describe what the material covers.

    Only chunks headed by a real noun are kept — this is what stops the
    generator from producing questions built around "it", "each node" or
    "the following operations".
    """
    candidates: list[str] = []
    nlp = _load_spacy()
    if nlp:
        doc = nlp(text[:400_000])
        for chunk in doc.noun_chunks:
            if chunk.root.pos_ not in ("NOUN", "PROPN"):
                continue
            tokens = _strip_leading_determiners(chunk.text.strip().split())
            if not tokens:
                continue
            phrase = " ".join(tokens).lower()
            head = tokens[-1].lower()
            if head in _JUNK_HEADS or phrase in _JUNK_HEADS:
                continue
            if len(tokens) > 4:            # long chunks are usually mis-parsed clauses, not terms
                continue
            if len(tokens) == 1 and phrase in GENERIC_UNIGRAMS:
                continue
            if 3 < len(phrase) < 45 and not phrase.isdigit() and phrase.isascii():
                candidates.append(phrase)
    if not candidates:
        candidates = re.findall(r"\b[A-Za-z][A-Za-z\-]{3,}(?:\s+[A-Za-z][A-Za-z\-]{3,}){0,2}\b", text)
        candidates = [c.lower() for c in candidates]

    if not candidates:
        return []

    vec = TfidfVectorizer(ngram_range=(1, 3), stop_words="english", max_features=4000)
    try:
        matrix = vec.fit_transform(candidates)
    except ValueError:
        return []
    scores = matrix.sum(axis=0).A1
    feature_names = vec.get_feature_names_out()
    # A generic word said 40 times can out-score a specific term said 5 times
    # on raw TF-IDF sum alone. Weighting by word count favours the specific,
    # multi-word technical term over sheer repetition of a common noun.
    weighted = [(name, score * (1 + 0.6 * (len(name.split()) - 1))) for name, score in zip(feature_names, scores)]
    ranked = sorted(weighted, key=lambda x: -x[1])

    def _dedup_key(word: str) -> str:
        # Naive singularization so "tuple"/"tuples" or "relation"/"relations"
        # collapse to the same dedup key. Without this, plural and singular
        # forms of one concept both survive as "different" topics, and a
        # template can then pair a word against its own plural ("role of
        # tuples in the context of tuple") — not an exact-string self-match,
        # so the existing self-reference guard doesn't catch it either.
        return word[:-1] if word.endswith("s") and len(word) > 3 else word

    topics, seen = [], set()
    for phrase, _ in ranked:
        head = phrase.split()[-1]
        key = _dedup_key(head)
        if key in seen:
            continue
        seen.add(key)
        topics.append(phrase)
        if len(topics) == top_k:
            break
    return topics


def rank_sentences(sentences: list[str], topics: list[str]) -> list[tuple[str, str]]:
    """Pair each informative sentence with the topic it best covers."""
    pairs = []
    for sent in sentences:
        lowered = sent.lower()
        hit = next((t for t in topics if t in lowered), None)
        if hit:
            pairs.append((sent, hit))
    random.shuffle(pairs)
    return pairs


# ------------------------------------------------------------- distractors
def build_distractors(answer: str, topics: list[str], n: int = 3) -> list[str]:
    """Plausible wrong options: nearest topics by embedding, else WordNet, else siblings."""
    pool = [t for t in topics if t.lower() != answer.lower()]
    embedder = load_embedder()
    if embedder and pool:
        import numpy as np

        vecs = embedder.encode([answer] + pool, normalize_embeddings=True)
        sims = np.dot(vecs[1:], vecs[0])
        order = sims.argsort()[::-1]
        # skip near-duplicates (sim > 0.92) so options aren't secretly correct
        picked = [pool[i] for i in order if sims[i] < 0.92][:n]
        if len(picked) == n:
            return picked

    try:
        from nltk.corpus import wordnet as wn

        out: list[str] = []
        for syn in wn.synsets(answer.split()[-1])[:3]:
            for hyper in syn.hypernyms():
                for sibling in hyper.hyponyms():
                    word = sibling.lemmas()[0].name().replace("_", " ")
                    if word.lower() != answer.lower() and word not in out:
                        out.append(word)
        if len(out) >= n:
            return out[:n]
    except Exception:
        pass

    fallback = pool[:n]
    while len(fallback) < n:
        fallback.append(f"None of the above ({len(fallback)})")
    return fallback[:n]


# --------------------------------------------------------------- grammar
_DUPLICATE_WORD = re.compile(r"\b(\w+)(\s+\1)+\b", flags=re.I)
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:?!])")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_PUNCT = re.compile(r"([.?!]){2,}")


def _grammar_clean(text: str) -> str:
    """Fix the artifacts template-filling and blanking tend to leave behind:
    doubled words ("the the"), stray space before a comma, run-on punctuation,
    and a missing capital at the start of the sentence."""
    text = _MULTI_SPACE.sub(" ", text).strip()
    text = _DUPLICATE_WORD.sub(r"\1", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _MULTI_PUNCT.sub(r"\1", text)
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    if text and text[-1] not in ".?!":
        text += "." if not text.rstrip().endswith("__________") else ""
    return text


# ------------------------------------------------------------- question gen
@dataclass
class GeneratedQuestion:
    text: str
    qtype: str
    marks: int
    difficulty: str = "medium"
    topic: str | None = None
    answer_key: str = ""
    options: list[str] = field(default_factory=list)


def _blank_out(sentence: str, topic: str) -> tuple[str, str] | None:
    """Turn a sentence into a fill-in / MCQ stem by hiding the key phrase."""
    match = re.search(re.escape(topic), sentence, flags=re.I)
    if not match:
        return None
    answer = sentence[match.start():match.end()]
    stem = sentence[:match.start()] + "__________" + sentence[match.end():]
    return stem, answer


def _difficulty_for(index: int, mix: dict[str, int]) -> str:
    order = ["easy", "medium", "hard"]
    weights = [max(mix.get(k, 0), 0) for k in order]
    if sum(weights) == 0:
        return "medium"
    return random.choices(order, weights=weights, k=1)[0]


def _build_model_answer(topic: str, pairs: list[tuple[str, str]], marks: int, qtype: str) -> str:
    """Assemble a model answer sized to what the question is worth.

    This is still extractive — every sentence comes from the uploaded
    material, nothing is invented, which is also what keeps grading
    consistent (the grader compares a student's answer against exactly
    this text). But a 2-mark question and an 8-mark question were getting
    the same lump of concatenated sentences; this scales how much gets
    pulled in, drops near-duplicate sentences, and — for long answers —
    lays it out as numbered points instead of one run-on paragraph, so it
    reads like a written answer rather than a pasted excerpt.
    """
    seen, support = set(), []
    for sent, t in pairs:
        if t != topic:
            continue
        key = sent.lower()[:60]          # cheap near-duplicate guard
        if key in seen:
            continue
        seen.add(key)
        support.append(_grammar_clean(sent))

    if not support:
        return ""

    # roughly one point per 2 marks: a 2-mark question gets one sentence,
    # an 8-mark question gets up to four, capped at six so it never balloons
    # into the entire source paragraph.
    target = max(1, min(6, round(marks / 2)))
    chosen = support[:target]

    if qtype == "long" and len(chosen) > 1:
        return " ".join(f"{i}) {s}" for i, s in enumerate(chosen, start=1))
    return " ".join(chosen)


# ------------------------------------------------------------- pretrained QG
# Optional upgrade over template-filling. Given a real sentence from the
# material and the phrase that should be the answer, a model fine-tuned for
# question generation (not just general text generation) composes an actual
# question — not a template with a blank filled in. Requires
# `pip install transformers torch` and a one-time ~850MB model download the
# first time it runs; if either isn't available, every caller below falls
# back to the existing template approach automatically. This is the same
# lazy-load-with-fallback pattern already used for spaCy and sentence-transformers.
_qg_pipeline = None


def _load_qg_pipeline():
    global _qg_pipeline
    if _qg_pipeline is None:
        try:
            from transformers import pipeline as hf_pipeline

            _qg_pipeline = hf_pipeline(
                "text2text-generation",
                model="mrm8488/t5-base-finetuned-question-generation-ap",
            )
        except Exception:
            _qg_pipeline = False          # sentinel: unavailable, don't retry every call
    return _qg_pipeline or None


def generate_with_pretrained_model(sentence: str, answer: str) -> str | None:
    """Compose a fluent question whose answer is `answer`, grounded in
    `sentence`. Returns None — not an exception — if the model isn't
    installed or the output looks unusable, so callers can fall back
    to template-filling without needing a try/except of their own."""
    pipe = _load_qg_pipeline()
    if not pipe or not sentence or not answer:
        return None
    prompt = f"answer: {answer} context: {sentence}"
    try:
        result = pipe(prompt, max_length=64, num_return_sequences=1)
        text = (result[0].get("generated_text") or "").strip()
    except Exception:
        return None
    if len(text.split()) < 3:             # too short to be a real question
        return None
    return _grammar_clean(text)


def generate_questions(
    text: str,
    qtype: str,
    count: int,
    marks_each: int,
    topics: list[str] | None = None,
    difficulty_mix: dict[str, int] | None = None,
) -> list[GeneratedQuestion]:
    difficulty_mix = difficulty_mix or {"easy": 35, "medium": 45, "hard": 20}
    topics = topics or extract_topics(text)
    sentences = split_sentences(text)
    pairs = rank_sentences(sentences, topics)

    out: list[GeneratedQuestion] = []
    used_stems: set[str] = set()

    for i in range(count):
        difficulty = _difficulty_for(i, difficulty_mix)

        if qtype in ("mcq", "fill"):
            made = None
            for sent, topic in pairs:
                blanked = _blank_out(sent, topic)
                if blanked and blanked[0] not in used_stems:
                    made = (blanked[0], blanked[1], topic)
                    used_stems.add(blanked[0])
                    break
            if not made:
                continue
            stem, answer, topic = made
            q = GeneratedQuestion(
                text=_grammar_clean(stem), qtype=qtype, marks=marks_each,
                difficulty=difficulty, topic=topic, answer_key=answer,
            )
            if qtype == "mcq":
                options = [answer] + build_distractors(answer, topics)
                random.shuffle(options)
                q.options = options
            out.append(q)

        else:  # short / long
            if not topics:
                break
            topic = topics[i % len(topics)]
            # pick a DIFFERENT topic for the broader context slot, so a template
            # never fills both blanks with the same word ("role of X in X").
            other_topics = [t for t in topics if t != topic]
            broader = random.choice(other_topics) if other_topics else topic

            # Try the pretrained model first — it composes an original question
            # instead of filling a blank, grounded in a real sentence from the
            # material rather than a bare topic word.
            support_sentence = next((s for s, t in pairs if t == topic), None)
            question_text = (
                generate_with_pretrained_model(support_sentence, topic)
                if support_sentence else None
            )
            if not question_text:
                template = random.choice(SHORT_TEMPLATES if qtype == "short" else LONG_TEMPLATES)
                question_text = _grammar_clean(template.format(concept=topic, topic=broader))

            if question_text in used_stems:
                continue
            used_stems.add(question_text)
            model_answer = _build_model_answer(topic, pairs, marks_each, qtype)
            if not model_answer:
                # No sentence in the material actually supports this topic —
                # shipping a question with no answer is worse than shipping
                # one fewer question. Skip it rather than include it anyway.
                used_stems.discard(question_text)
                continue
            out.append(GeneratedQuestion(
                text=question_text,
                qtype=qtype, marks=marks_each, difficulty=difficulty,
                topic=topic, answer_key=model_answer,
            ))

    return out
