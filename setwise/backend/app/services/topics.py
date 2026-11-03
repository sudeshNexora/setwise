"""
Lightweight key-term extraction.

With an LLM writing the questions, topics are only needed in two places:
the topic chips shown on the Upload page, and the keyword-coverage part of
answer grading. So this stays dependency-free (no spaCy, no scikit-learn):
split the text into runs of content words, count 1-3 word phrases, and rank
phrases that repeat, favouring multi-word terms over bare generic nouns.
"""
from __future__ import annotations

import re
from collections import Counter

_STOPWORDS = set(
    """
    a about above after again against all also am an and any are aren as at be because been before being
    below between both but by can cannot could did do does doing don down during each either else etc few
    for from further had has have having he her here hers him his how however i if in into is it its itself
    just let like may me might more most must my no nor not of off on once only or other ought our ours out
    over own per same shall she should so some such than that the their theirs them then there these they
    this those through thus to too under until up upon us use used uses using very via was we were what
    when where whether which while who whom whose why will with within without would yet you your yours
    one two three four first second third example examples following called known given called often
    usually generally typically hence therefore means mean given need needs make makes made take takes
    """.split()
)

# Words that are real nouns but say nothing about WHAT was taught. They are
# rejected as a stand-alone topic and remain fine inside a longer term
# ("training data", "relation schema").
GENERIC_UNIGRAMS = {
    "data", "model", "models", "figure", "figures", "table", "tables", "example", "examples",
    "method", "methods", "approach", "approaches", "system", "systems", "process", "processes",
    "type", "types", "case", "cases", "feature", "features", "information", "result", "results",
    "way", "ways", "number", "form", "forms", "aspect", "aspects", "part", "parts", "point",
    "points", "value", "values", "item", "items", "concept", "concepts", "unit", "units",
    "chapter", "chapters", "page", "pages", "section", "sections", "note", "notes", "set", "sets",
    "list", "operation", "thing", "things", "set", "name", "names", "level", "levels", "time",
}


def _singular_key(word: str) -> str:
    """Cheap singularisation so tuple/tuples or relation/relations count as one term."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _runs(text: str) -> list[list[str]]:
    """Maximal runs of consecutive content words (no stopwords, no punctuation)."""
    runs: list[list[str]] = []
    # anything that is not a letter, hyphen or whitespace is a hard break
    for segment in re.split(r"[^A-Za-z\-\s]+", text.lower()):
        current: list[str] = []
        for token in segment.split():
            token = token.strip("-")
            if len(token) >= 3 and token not in _STOPWORDS:
                current.append(token)
            else:
                if current:
                    runs.append(current)
                current = []
        if current:
            runs.append(current)
    return runs


def extract_topics(text: str, top_k: int = 12) -> list[str]:
    """Most characteristic key terms of `text`, best first.

    A term has to appear at least twice to count as a topic of long study material.
    """
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    position = 0

    for run in _runs(text):
        for size in (1, 2, 3):
            for i in range(0, len(run) - size + 1):
                phrase = " ".join(run[i:i + size])
                if size == 1 and (phrase in GENERIC_UNIGRAMS or len(phrase) < 4):
                    continue
                if size > 1 and (run[i] in GENERIC_UNIGRAMS and run[i + size - 1] in GENERIC_UNIGRAMS):
                    continue
                counts[phrase] += 1
                first_seen.setdefault(phrase, position)
                position += 1

    scored = []
    for phrase, count in counts.items():
        if count < 2:
            continue
        words = phrase.count(" ") + 1
        scored.append((count * (1 + 0.6 * (words - 1)), -first_seen[phrase], phrase, count))
    scored.sort(reverse=True)

    topics: list[str] = []
    chosen_counts: list[tuple[str, int]] = []
    seen_heads: set[str] = set()
    for _, _, phrase, count in scored:
        head = _singular_key(phrase.split()[-1])
        if head in seen_heads:
            continue
        # skip a fragment of a longer term we already picked ("relational" when
        # "relational algebra" was chosen) unless it is clearly more common
        padded = f" {phrase} "
        if any(padded in f" {other} " and count <= 1.5 * other_count for other, other_count in chosen_counts):
            continue
        seen_heads.add(head)
        chosen_counts.append((phrase, count))
        topics.append(phrase)
        if len(topics) == top_k:
            break
    return topics


def content_words(text: str) -> dict[str, str]:
    """The meaningful words of `text` as {stem: first spelling}.

    Used by the grader: comparing stems makes "tuple"/"tuples" and
    "identify"/"identifies" count as the same word, and dropping stopwords and
    generic nouns leaves the words that actually carry the answer.
    """
    words: dict[str, str] = {}
    for word in re.findall(r"[a-z][a-z\-]*[a-z]", text.lower()):
        if len(word) < 3 or word in _STOPWORDS or word in GENERIC_UNIGRAMS:
            continue
        words.setdefault(_singular_key(word), word)
    return words
