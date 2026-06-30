"""Domain-general candidate-term discovery.

The curated ontology in ``concept_extractor`` gives high precision on quantum
computing, but a dataset meant to *generally* train scientific reasoning must
grow its concept vocabulary from whatever literature it is fed. This module
mines candidate concepts from raw text with pure-regex heuristics — no NLP
dependency — so the index expands automatically on any corpus.

Three complementary signals:
  1. Acronym + definition:  "Quantum Phase Estimation (QPE)"   — highest value.
  2. Suffix noun-phrases:    "... transverse-field Ising model" — scientific
     head-noun suffixes that generalize across fields.
  3. Standalone acronyms:    "... using DMRG ..."              — low value alone,
     promoted only when frequent.

Each candidate is typed by its head-noun suffix so promoted concepts slot into
the same type system (method / model / ansatz / math_object / field).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Head-noun suffixes that reliably mark a scientific concept, mapped to a type.
SUFFIX_TYPE: dict[str, str] = {
    "ansatz": "ansatz", "ansatze": "ansatz", "ansätze": "ansatz",
    "algorithm": "method", "method": "method", "solver": "method",
    "optimizer": "method", "protocol": "method", "scheme": "method",
    "decomposition": "method", "transform": "method", "simulation": "method",
    "model": "model", "hamiltonian": "model",
    "theory": "field", "framework": "field", "formalism": "field",
    "network": "field", "networks": "field",
    "state": "math_object", "states": "math_object", "operator": "math_object",
    "equation": "math_object", "inequality": "math_object", "bound": "math_object",
    "theorem": "math_object", "lemma": "math_object", "distribution": "math_object",
    "ensemble": "math_object", "kernel": "math_object", "embedding": "math_object",
    "encoding": "math_object", "mapping": "math_object", "representation": "math_object",
    "spectrum": "math_object", "entropy": "math_object", "metric": "math_object",
    "gate": "method", "code": "method", "circuit": "method",
}

_SUFFIX_ALT = "|".join(sorted((re.escape(s) for s in SUFFIX_TYPE), key=len, reverse=True))

# A phrase = 1–3 content words followed by a known head-noun suffix.
_PHRASE_RE = re.compile(
    rf"\b([a-z][a-z\-]+(?:\s+[a-z][a-z\-]+){{0,3}}\s+(?:{_SUFFIX_ALT}))\b",
    re.IGNORECASE,
)

# Long-Form (ACR) definition pattern.
_ACRONYM_DEF_RE = re.compile(
    r"\b((?:[A-Za-z][\w\-]*\s+){1,6}[A-Za-z][\w\-]*)\s*\(([A-Z][A-Za-z]{1,7})s?\)"
)

# Bare acronyms in running text.
_BARE_ACRONYM_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,6})\b")

# Words that must not start a candidate phrase (determiners / vague heads).
_LEADING_STOP = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "our", "their", "its",
    "such", "new", "recent", "present", "proposed", "same", "given", "above",
    "following", "first", "second", "third", "main", "general", "simple", "other",
    "each", "any", "some", "all", "both", "two", "three", "one", "single",
})

# Acronyms that are ordinary English / not concepts.
_ACRONYM_STOP = frozenset({
    "AND", "THE", "FOR", "WITH", "FROM", "THIS", "THAT", "USING", "WHEN",
    "WHERE", "WHICH", "THESE", "THOSE", "OUR", "ALL", "ONE", "TWO", "III",
    "II", "IV", "VI", "VII", "NOT", "CAN", "MAY", "ARE", "WAS", "HAS", "HAD",
    "USA", "PDF", "HTML", "URL", "API", "FAQ",
})


@dataclass
class MinedTerm:
    term: str                 # lower-cased canonical surface form
    display: str              # best-cased display form
    acronym: str = ""
    inferred_type: str = ""
    count: int = 1            # mentions within the current document

    def merge(self, other: "MinedTerm") -> None:
        self.count += other.count
        if not self.acronym and other.acronym:
            self.acronym = other.acronym
        if not self.inferred_type and other.inferred_type:
            self.inferred_type = other.inferred_type
        if other.display and other.display[0].isupper() and not self.display[0].isupper():
            self.display = other.display


def _type_for_suffix(phrase: str) -> str:
    last = phrase.rsplit(None, 1)[-1].lower()
    return SUFFIX_TYPE.get(last, "")


def _clean_phrase(phrase: str) -> str | None:
    """Drop leading stopwords; reject if nothing contentful remains."""
    words = phrase.split()
    while words and words[0].lower() in _LEADING_STOP:
        words = words[1:]
    if len(words) < 2:  # need at least one modifier + head noun
        return None
    if all(len(w) <= 2 for w in words):
        return None
    return " ".join(words)


def _acronym_matches(long_form: str, acronym: str) -> str | None:
    """Return the trimmed long form if its word initials match the acronym."""
    words = [w for w in re.split(r"[\s\-]+", long_form) if w]
    acr = acronym.lower()
    # Try the trailing len(acr) words first (typical "... Long Form (LF)").
    for span in range(len(acr), len(acr) + 3):
        window = words[-span:] if span <= len(words) else words
        initials = "".join(w[0].lower() for w in window if w)
        if initials.endswith(acr) or acr in initials:
            return " ".join(window)
    # Fallback: first letters of all words contain the acronym in order.
    initials = "".join(w[0].lower() for w in words)
    if acr in initials:
        return long_form
    return None


def mine_document(text: str) -> dict[str, MinedTerm]:
    """Mine candidate concept terms from one document's text.

    Returns a map ``lower_term -> MinedTerm`` with per-document mention counts.
    """
    found: dict[str, MinedTerm] = {}

    def add(term: MinedTerm) -> None:
        key = term.term
        if key in found:
            found[key].merge(term)
        else:
            found[key] = term

    # 1) Acronym + definition (highest confidence)
    defined_acronyms: dict[str, str] = {}
    for m in _ACRONYM_DEF_RE.finditer(text):
        long_form_raw, acronym = m.group(1).strip(), m.group(2).strip()
        matched = _acronym_matches(long_form_raw, acronym)
        if not matched:
            continue
        cleaned = _clean_phrase(matched)
        if not cleaned:
            continue
        defined_acronyms[acronym.upper()] = cleaned.lower()
        add(MinedTerm(
            term=cleaned.lower(),
            display=cleaned,
            acronym=acronym.upper(),
            inferred_type=_type_for_suffix(cleaned),
        ))

    # 2) Suffix noun-phrases
    for m in _PHRASE_RE.finditer(text):
        cleaned = _clean_phrase(m.group(1).strip())
        if not cleaned:
            continue
        add(MinedTerm(
            term=cleaned.lower(),
            display=cleaned,
            inferred_type=_type_for_suffix(cleaned),
        ))

    # 3) Bare acronyms — only those we saw defined, or clearly technical.
    for m in _BARE_ACRONYM_RE.finditer(text):
        acr = m.group(1).upper()
        if acr in _ACRONYM_STOP or len(acr) < 2:
            continue
        if acr in defined_acronyms:
            # Reinforce the defined long-form's count instead of the bare form.
            add(MinedTerm(term=defined_acronyms[acr], display=defined_acronyms[acr]))
        else:
            add(MinedTerm(term=acr.lower(), display=acr, acronym=acr))

    return found


def salience(term: MinedTerm, doc_frequency: int) -> float:
    """Rank candidates: corpus reach, multiword specificity, acronym evidence."""
    n_words = len(term.term.split())
    length_weight = 1.0 + 0.25 * (n_words - 1)
    acronym_bonus = 1.4 if term.acronym else 1.0
    type_bonus = 1.2 if term.inferred_type else 1.0
    return round(doc_frequency * length_weight * acronym_bonus * type_bonus, 3)


def is_promotable(
    term: MinedTerm, doc_frequency: int, *, min_docs: int = 3
) -> bool:
    """Should this candidate become a first-class concept?

    Promote if it has a verified acronym definition, or it is a typed multiword
    phrase seen in at least ``min_docs`` papers.
    """
    if term.acronym and len(term.term.split()) >= 2:
        return True
    if term.inferred_type and len(term.term.split()) >= 2 and doc_frequency >= min_docs:
        return True
    return False
