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
def split_sentences(text: str) -> list[str]:
    nlp = _load_spacy()
    if nlp:
        doc = nlp(text[:900_000])
        sents = [s.text.strip() for s in doc.sents]
    else:
        sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if 40 <= len(s.strip()) <= 320]


# ----------------------------------------------------------------- concepts
def extract_topics(text: str, top_k: int = 12) -> list[str]:
    """Keyphrases that describe what the material covers."""
    candidates: list[str] = []
    nlp = _load_spacy()
    if nlp:
        doc = nlp(text[:400_000])
        for chunk in doc.noun_chunks:
            phrase = chunk.text.strip().lower()
            if phrase.split()[0] in STOP_START:
                phrase = " ".join(phrase.split()[1:])
            if 3 < len(phrase) < 45 and not phrase.isdigit():
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
    ranked = sorted(zip(vec.get_feature_names_out(), scores), key=lambda x: -x[1])

    topics, seen = [], set()
    for phrase, _ in ranked:
        head = phrase.split()[-1]
        if head in seen:
            continue
        seen.add(head)
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
                text=stem, qtype=qtype, marks=marks_each,
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
            broader = topics[0] if topics else topic
            template = random.choice(SHORT_TEMPLATES if qtype == "short" else LONG_TEMPLATES)
            stem = template.format(concept=topic, topic=broader)
            if stem in used_stems:
                continue
            used_stems.add(stem)
            # model answer = the sentences from the material that mention the topic
            support = [s for s, t in pairs if t == topic][:3]
            out.append(GeneratedQuestion(
                text=stem[0].upper() + stem[1:],
                qtype=qtype, marks=marks_each, difficulty=difficulty,
                topic=topic, answer_key=" ".join(support),
            ))

    return out
