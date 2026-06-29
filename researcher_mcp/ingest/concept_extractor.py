"""Deterministic concept extraction for the synthesis engine.

Given a paper's title + abstract (+ optional full text), extracts:
- Atomic concepts: named techniques, ansätze, models, math objects, benchmarks
- Typed relations: how concepts connect within and across papers

No paid API. Pure regex + curated quantum-computing ontology.
Concept mentions → paper_concepts table.
Relations → concept_edges table (weighted).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Ontology
# ---------------------------------------------------------------------------

class ConceptMeta(NamedTuple):
    type: str         # method | ansatz | problem | model | math_object | benchmark | field | hardware
    aliases: tuple[str, ...]   # lower-cased; first entry is the canonical display alias
    description: str  # human-readable label


# Canonical key (stable, lower-cased slug) → meta
CONCEPT_REGISTRY: dict[str, ConceptMeta] = {

    # ── Methods ──────────────────────────────────────────────────────────────
    "vqe": ConceptMeta(
        "method",
        ("variational quantum eigensolver", "vqe"),
        "Variational Quantum Eigensolver (VQE)",
    ),
    "adapt-vqe": ConceptMeta(
        "method",
        ("adapt-vqe", "adapt vqe", "adaptive vqe"),
        "ADAPT-VQE",
    ),
    "qaoa": ConceptMeta(
        "method",
        ("quantum approximate optimization algorithm", "qaoa"),
        "QAOA",
    ),
    "qpe": ConceptMeta(
        "method",
        ("quantum phase estimation", "qpe"),
        "Quantum Phase Estimation",
    ),
    "vqd": ConceptMeta(
        "method",
        ("variational quantum deflation", "vqd"),
        "Variational Quantum Deflation",
    ),
    "qite": ConceptMeta(
        "method",
        ("quantum imaginary time evolution", "qite"),
        "Quantum Imaginary Time Evolution",
    ),
    "dmrg": ConceptMeta(
        "method",
        ("density matrix renormalization group", "dmrg"),
        "Density Matrix Renormalization Group (DMRG)",
    ),
    "dmet": ConceptMeta(
        "method",
        ("density matrix embedding theory", "dmet"),
        "Density Matrix Embedding Theory (DMET)",
    ),
    "circuit-cutting": ConceptMeta(
        "method",
        ("circuit cutting", "circuit-cutting"),
        "Circuit Cutting",
    ),
    "circuit-knitting": ConceptMeta(
        "method",
        ("circuit knitting", "adaptive circuit knitting"),
        "Circuit Knitting",
    ),
    "tensor-network-contraction": ConceptMeta(
        "method",
        ("tensor network contraction", "tensor contraction"),
        "Tensor Network Contraction",
    ),
    "trotter-decomposition": ConceptMeta(
        "method",
        ("trotter decomposition", "trotterization", "suzuki-trotter", "trotter-suzuki", "trotter step", "product formula"),
        "Trotter / Suzuki-Trotter Decomposition",
    ),
    "zne": ConceptMeta(
        "method",
        ("zero noise extrapolation", "zero-noise extrapolation", "zne"),
        "Zero Noise Extrapolation (ZNE)",
    ),
    "pec": ConceptMeta(
        "method",
        ("probabilistic error cancellation", "pec"),
        "Probabilistic Error Cancellation (PEC)",
    ),
    "qml": ConceptMeta(
        "method",
        ("quantum machine learning",),
        "Quantum Machine Learning (QML)",
    ),
    "qsvm": ConceptMeta(
        "method",
        ("quantum support vector machine", "quantum svm", "qsvm"),
        "Quantum Support Vector Machine",
    ),
    "qnn": ConceptMeta(
        "method",
        ("quantum neural network", "qnn"),
        "Quantum Neural Network (QNN)",
    ),
    "quantum-kernel": ConceptMeta(
        "method",
        ("quantum kernel", "quantum kernel method"),
        "Quantum Kernel Method",
    ),
    "pauli-grouping": ConceptMeta(
        "method",
        ("pauli grouping", "pauli decomposition", "pauli partitioning"),
        "Pauli Grouping",
    ),
    "shadow-tomography": ConceptMeta(
        "method",
        ("shadow tomography", "classical shadow", "classical shadows"),
        "Classical Shadow Tomography",
    ),
    "randomized-benchmarking": ConceptMeta(
        "method",
        ("randomized benchmarking",),
        "Randomized Benchmarking",
    ),
    "fci": ConceptMeta(
        "method",
        ("full configuration interaction", "full ci"),
        "Full Configuration Interaction (FCI)",
    ),
    "hartree-fock": ConceptMeta(
        "method",
        ("hartree-fock",),
        "Hartree-Fock",
    ),
    "coupled-cluster": ConceptMeta(
        "method",
        ("coupled cluster", "ccsd", "uccsd ansatz"),
        "Coupled Cluster",
    ),
    "natural-gradient": ConceptMeta(
        "method",
        ("quantum natural gradient", "natural gradient", "qng"),
        "Quantum Natural Gradient",
    ),
    "parameter-shift": ConceptMeta(
        "method",
        ("parameter-shift rule", "parameter shift rule", "parameter shift"),
        "Parameter-Shift Rule",
    ),
    "hamiltonian-simulation": ConceptMeta(
        "method",
        ("hamiltonian simulation", "quantum simulation of hamiltonian"),
        "Hamiltonian Simulation",
    ),
    "vqls": ConceptMeta(
        "method",
        ("variational quantum linear solver", "vqls"),
        "Variational Quantum Linear Solver (VQLS)",
    ),
    "mps-compression": ConceptMeta(
        "method",
        ("mps compression", "tensor train compression", "tensor train decomposition"),
        "MPS / Tensor-Train Compression",
    ),
    "quantum-feature-map": ConceptMeta(
        "method",
        ("quantum feature map", "data re-uploading", "data reuploading"),
        "Quantum Feature Map / Data Re-uploading",
    ),
    "swap-network": ConceptMeta(
        "method",
        ("swap network", "fermionic swap network"),
        "SWAP Network",
    ),

    # ── Ansätze ──────────────────────────────────────────────────────────────
    "mps": ConceptMeta(
        "ansatz",
        ("matrix product state", "matrix product states", "matrix-product state", "tensor train"),
        "Matrix Product State (MPS / Tensor Train)",
    ),
    "mera": ConceptMeta(
        "ansatz",
        ("multiscale entanglement renormalization ansatz", "multi-scale entanglement renormalization ansatz", "mera"),
        "MERA",
    ),
    "peps": ConceptMeta(
        "ansatz",
        ("projected entangled pair states", "projected entangled-pair states", "peps"),
        "PEPS",
    ),
    "qmera": ConceptMeta(
        "ansatz",
        ("qmera", "q-mera", "quantum mera"),
        "Quantum MERA (QMERA)",
    ),
    "qpeps": ConceptMeta(
        "ansatz",
        ("qpeps", "q-peps", "quantum peps"),
        "Quantum PEPS (QPEPS)",
    ),
    "ttns": ConceptMeta(
        "ansatz",
        ("tree tensor network state", "tree tensor network"),
        "Tree Tensor Network State (TTNS)",
    ),
    "uccsd": ConceptMeta(
        "ansatz",
        ("unitary coupled cluster singles and doubles", "uccsd", "ucc ansatz", "uccgsd"),
        "UCCSD Ansatz",
    ),
    "hardware-efficient-ansatz": ConceptMeta(
        "ansatz",
        ("hardware-efficient ansatz", "hardware efficient ansatz", "hardware-efficient circuit"),
        "Hardware-Efficient Ansatz (HEA)",
    ),
    "ry-ansatz": ConceptMeta(
        "ansatz",
        ("ry ansatz", "ry circuit", "ry layer"),
        "Ry Ansatz",
    ),
    "brickwork-ansatz": ConceptMeta(
        "ansatz",
        ("checkerboard ansatz", "checkerboard circuit", "brick-layer ansatz", "brick layer ansatz", "brickwork ansatz", "alternating layered ansatz"),
        "Brick-Layer / Brickwork Ansatz",
    ),
    "unitary-design": ConceptMeta(
        "ansatz",
        ("2-design", "two-design", "unitary 2-design", "unitary design", "approximate unitary design"),
        "Unitary 2-Design",
    ),
    "qpeps-qmera": ConceptMeta(
        "ansatz",
        ("qpeps-qmera", "qmera-qpeps", "hybrid qpeps-qmera", "hybrid qmera-qpeps"),
        "Hybrid QPEPS-QMERA Ansatz",
    ),

    # ── Problems ─────────────────────────────────────────────────────────────
    "ground-state-energy": ConceptMeta(
        "problem",
        ("ground state energy", "ground-state energy", "ground state estimation", "ground-state estimation"),
        "Ground State Energy Estimation",
    ),
    "ground-state-preparation": ConceptMeta(
        "problem",
        ("ground state preparation", "ground-state preparation"),
        "Ground State Preparation",
    ),
    "electronic-structure": ConceptMeta(
        "problem",
        ("electronic structure", "molecular electronic structure"),
        "Electronic Structure",
    ),
    "quantum-chemistry": ConceptMeta(
        "problem",
        ("quantum chemistry",),
        "Quantum Chemistry",
    ),
    "quantum-error-correction": ConceptMeta(
        "problem",
        ("quantum error correction", "error correction"),
        "Quantum Error Correction",
    ),
    "quantum-error-mitigation": ConceptMeta(
        "problem",
        ("quantum error mitigation", "error mitigation", "noise mitigation"),
        "Quantum Error Mitigation",
    ),
    "quantum-optimization": ConceptMeta(
        "problem",
        ("quantum optimization", "combinatorial optimization", "variational optimization"),
        "Quantum Optimization",
    ),
    "lattice-gauge": ConceptMeta(
        "problem",
        ("lattice gauge theory", "lattice field theory"),
        "Lattice Gauge Theory",
    ),
    "quantum-advantage": ConceptMeta(
        "problem",
        ("quantum advantage", "quantum supremacy", "computational advantage"),
        "Quantum Advantage",
    ),
    "barren-plateau": ConceptMeta(
        "problem",
        ("barren plateau", "barren plateaus", "vanishing gradient", "gradient vanishing", "trainability"),
        "Barren Plateau / Vanishing Gradient",
    ),
    "quantum-noise": ConceptMeta(
        "problem",
        ("decoherence", "depolarizing noise", "gate error", "noise model"),
        "Quantum Noise / Decoherence",
    ),

    # ── Models ───────────────────────────────────────────────────────────────
    "tfim": ConceptMeta(
        "model",
        ("transverse field ising model", "transverse-field ising model", "transverse ising model", "tfim"),
        "Transverse-Field Ising Model (TFIM)",
    ),
    "ising-model": ConceptMeta(
        "model",
        ("ising model",),
        "Ising Model",
    ),
    "heisenberg-model": ConceptMeta(
        "model",
        ("heisenberg model", "heisenberg chain", "heisenberg spin chain"),
        "Heisenberg Model",
    ),
    "xxz-model": ConceptMeta(
        "model",
        ("xxz model", "xxz chain", "xxz spin chain"),
        "XXZ Model",
    ),
    "hubbard-model": ConceptMeta(
        "model",
        ("hubbard model", "fermi-hubbard model", "fermi hubbard model"),
        "Hubbard / Fermi-Hubbard Model",
    ),
    "bose-hubbard": ConceptMeta(
        "model",
        ("bose-hubbard model", "bose hubbard model"),
        "Bose-Hubbard Model",
    ),
    "kitaev-model": ConceptMeta(
        "model",
        ("kitaev model", "kitaev chain", "kitaev honeycomb"),
        "Kitaev Model",
    ),
    "schwinger-model": ConceptMeta(
        "model",
        ("schwinger model",),
        "Schwinger Model",
    ),
    "spin-chain": ConceptMeta(
        "model",
        ("spin chain", "spin-chain", "1d spin chain", "spin model"),
        "Spin Chain Model",
    ),
    "j1j2-model": ConceptMeta(
        "model",
        ("j1-j2 model", "j1j2 model", "frustrated spin", "frustrated magnet"),
        "J1-J2 / Frustrated Spin Model",
    ),

    # ── Math Objects ──────────────────────────────────────────────────────────
    "entanglement-entropy": ConceptMeta(
        "math_object",
        ("entanglement entropy", "von neumann entropy", "bipartite entanglement"),
        "Entanglement Entropy",
    ),
    "bond-dimension": ConceptMeta(
        "math_object",
        ("bond dimension", "virtual dimension"),
        "Bond Dimension",
    ),
    "qfim": ConceptMeta(
        "math_object",
        ("quantum fisher information matrix", "quantum fisher information", "fisher information matrix", "qfim"),
        "Quantum Fisher Information Matrix (QFIM)",
    ),
    "expressibility": ConceptMeta(
        "math_object",
        ("expressibility", "circuit expressibility", "expressive power"),
        "Circuit Expressibility",
    ),
    "entanglement-capacity": ConceptMeta(
        "math_object",
        ("entanglement capacity", "entanglement capability", "entanglement power"),
        "Entanglement Capacity",
    ),
    "density-matrix": ConceptMeta(
        "math_object",
        ("density matrix", "reduced density matrix"),
        "Density Matrix",
    ),
    "energy-landscape": ConceptMeta(
        "math_object",
        ("energy landscape", "loss landscape", "cost landscape", "optimization landscape"),
        "Energy / Loss Landscape",
    ),
    "pqc": ConceptMeta(
        "math_object",
        ("parameterized quantum circuit", "variational circuit"),
        "Parameterized Quantum Circuit (PQC)",
    ),
    "sampling-overhead": ConceptMeta(
        "math_object",
        ("sampling overhead", "shot overhead", "measurement overhead"),
        "Sampling Overhead",
    ),
    "entanglement-spectrum": ConceptMeta(
        "math_object",
        ("entanglement spectrum", "schmidt spectrum"),
        "Entanglement Spectrum",
    ),
    "area-law": ConceptMeta(
        "math_object",
        ("area law", "area-law entanglement", "entanglement area law"),
        "Entanglement Area Law",
    ),
    "quantum-state": ConceptMeta(
        "math_object",
        ("quantum state", "wave function", "wavefunction"),
        "Quantum State / Wave Function",
    ),
    "symmetry": ConceptMeta(
        "math_object",
        ("symmetry sector", "symmetry-preserving", "symmetry protection", "translational symmetry", "u(1) symmetry", "su(2) symmetry"),
        "Quantum Symmetry",
    ),
    "circuit-depth": ConceptMeta(
        "math_object",
        ("circuit depth", "gate depth", "layer depth"),
        "Circuit Depth",
    ),
    "gate-fidelity": ConceptMeta(
        "math_object",
        ("gate fidelity", "circuit fidelity"),
        "Gate / Circuit Fidelity",
    ),

    # ── Benchmarks ───────────────────────────────────────────────────────────
    "lih": ConceptMeta(
        "benchmark",
        ("lih", "lithium hydride"),
        "LiH Molecule",
    ),
    "beh2": ConceptMeta(
        "benchmark",
        ("beh2", "beryllium hydride"),
        "BeH2 Molecule",
    ),
    "h2o-molecule": ConceptMeta(
        "benchmark",
        ("water molecule",),
        "H2O Molecule",
    ),
    "hydrogen-chain": ConceptMeta(
        "benchmark",
        ("hydrogen chain",),
        "Hydrogen Chain",
    ),

    # ── Fields ───────────────────────────────────────────────────────────────
    "tensor-networks": ConceptMeta(
        "field",
        ("tensor network", "tensor networks"),
        "Tensor Networks",
    ),
    "variational-quantum-algorithms": ConceptMeta(
        "field",
        ("variational quantum algorithm", "variational quantum algorithms", "variational algorithm"),
        "Variational Quantum Algorithms (VQA)",
    ),
    "quantum-computing": ConceptMeta(
        "field",
        ("quantum computation",),
        "Quantum Computing",
    ),
    "quantum-information": ConceptMeta(
        "field",
        ("quantum information", "quantum information theory"),
        "Quantum Information",
    ),
    "distributed-quantum-computing": ConceptMeta(
        "field",
        ("distributed quantum computing", "distributed quantum computation"),
        "Distributed Quantum Computing",
    ),
    "fault-tolerant-qc": ConceptMeta(
        "field",
        ("fault-tolerant quantum computing", "fault tolerant quantum", "error-corrected quantum"),
        "Fault-Tolerant Quantum Computing",
    ),
    "nisq": ConceptMeta(
        "field",
        ("nisq", "noisy intermediate-scale quantum", "noisy intermediate scale quantum", "near-term quantum"),
        "NISQ / Near-Term Quantum",
    ),
    "quantum-simulation": ConceptMeta(
        "field",
        ("quantum simulation",),
        "Quantum Simulation",
    ),
    "quantum-computing-general": ConceptMeta(
        "field",
        ("quantum algorithm", "quantum algorithms"),
        "Quantum Algorithms",
    ),

    # ── Hardware ─────────────────────────────────────────────────────────────
    "superconducting": ConceptMeta(
        "hardware",
        ("superconducting qubit", "superconducting circuit", "transmon qubit"),
        "Superconducting Qubit",
    ),
    "trapped-ion": ConceptMeta(
        "hardware",
        ("trapped ion", "trapped-ion"),
        "Trapped-Ion Qubit",
    ),
    "neutral-atom": ConceptMeta(
        "hardware",
        ("neutral atom", "rydberg atom"),
        "Neutral-Atom Qubit",
    ),
    "photonic": ConceptMeta(
        "hardware",
        ("photonic quantum", "photonic chip"),
        "Photonic Quantum",
    ),
}

# Build flat lookup: alias → canonical key (longest aliases first so a more
# specific alias wins over a short one during scanning).
ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canon, _meta in CONCEPT_REGISTRY.items():
    for _alias in _meta.aliases:
        ALIAS_TO_CANONICAL[_alias] = _canon

# Short aliases (≤ 5 chars) that need strict word-boundary matching
SHORT_ALIASES: frozenset[str] = frozenset(a for a in ALIAS_TO_CANONICAL if len(a) <= 5)


# ---------------------------------------------------------------------------
# Relation patterns
# ---------------------------------------------------------------------------

_REL_DEFS: list[tuple[str, str]] = [
    # improves_on
    (r"\bimprove[sd]? (?:on|upon|over)\b", "improves_on"),
    (r"\boutperform[sd]?\b", "improves_on"),
    (r"\bbetter than\b", "improves_on"),
    (r"\bsuperior to\b", "improves_on"),
    (r"\badvantage over\b", "improves_on"),
    (r"\breduces? (?:the )?(?:error|overhead|cost|depth)\b", "improves_on"),
    # generalizes
    (r"\bextend[sd]?\b", "generalizes"),
    (r"\bgeneralize[sd]?\b", "generalizes"),
    (r"\bsubsume[sd]?\b", "generalizes"),
    (r"\ba generalization of\b", "generalizes"),
    (r"\bgeneralized version\b", "generalizes"),
    # applied_to — match "apply", "applied", "applied to", "apply X to"
    (r"\bapplied? to\b", "applied_to"),
    (r"\bappl(?:y|ied?)\b", "applied_to"),
    (r"\bused for\b", "applied_to"),
    (r"\bto solve\b", "applied_to"),
    (r"\bfor solving\b", "applied_to"),
    (r"\btackle[sd]?\b", "applied_to"),
    (r"\baddress(?:es|ed)?\b", "applied_to"),
    # combines — match verb regardless of following preposition
    (r"\bcombine[sd]? with\b", "combines"),
    (r"\bcombine[sd]?\b", "combines"),
    (r"\bcombining\b", "combines"),
    (r"\bhybrid of\b", "combines"),
    (r"\bintegrate[sd]? with\b", "combines"),
    (r"\bintegrating\b", "combines"),
    (r"\bcoupl(?:es|ed|ing)\b", "combines"),
    # requires
    (r"\brequire[sd]?\b", "requires"),
    (r"\bbased on\b", "requires"),
    (r"\bbuilt on\b", "requires"),
    (r"\bbuilds on\b", "requires"),
    (r"\brelies? on\b", "requires"),
    (r"\bderived from\b", "requires"),
    (r"\bbuilt upon\b", "requires"),
    # enables
    (r"\benable[sd]?\b", "enables"),
    (r"\bmakes? possible\b", "enables"),
    (r"\bfacilitate[sd]?\b", "enables"),
    (r"\ballows?\b", "enables"),
    # compared_to
    (r"\bcompared (?:to|with)\b", "compared_to"),
    (r"\bversus\b", "compared_to"),
    (r"\bvs\.?\b", "compared_to"),
    (r"\bagainst\b", "compared_to"),
    # benchmarked_on
    (r"\bbenchmark(?:ed)? (?:on|against)\b", "benchmarked_on"),
    (r"\btested on\b", "benchmarked_on"),
    (r"\bevaluated on\b", "benchmarked_on"),
    (r"\bdemonstrated on\b", "benchmarked_on"),
    (r"\bvalidated on\b", "benchmarked_on"),
]

# Weights for relation types (typed > co-occurrence)
RELATION_WEIGHT: dict[str, float] = {
    "improves_on": 1.5,
    "generalizes": 1.4,
    "combines": 1.3,
    "applied_to": 1.2,
    "requires": 1.1,
    "enables": 1.1,
    "benchmarked_on": 1.0,
    "compared_to": 0.8,
    "co_occurs": 0.3,
}

_COMPILED_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(p, re.IGNORECASE), r) for p, r in _REL_DEFS
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConceptMention:
    canonical: str       # key in CONCEPT_REGISTRY
    concept_type: str
    alias_found: str     # exact string that matched
    start: int           # char position in lower-cased text
    end: int


@dataclass
class ConceptRelation:
    source: str    # canonical key
    target: str    # canonical key
    relation: str  # one of RELATION_WEIGHT keys
    weight: float
    evidence: str  # truncated sentence for provenance


@dataclass
class ConceptExtractionResult:
    concepts: list[ConceptMention] = field(default_factory=list)
    relations: list[ConceptRelation] = field(default_factory=list)

    def unique_concept_names(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in self.concepts:
            if m.canonical not in seen:
                seen.add(m.canonical)
                out.append(m.canonical)
        return out

    def concept_scores(self) -> dict[str, float]:
        """Salience by normalized mention frequency."""
        counts: dict[str, int] = {}
        for m in self.concepts:
            counts[m.canonical] = counts.get(m.canonical, 0) + 1
        total = max(sum(counts.values()), 1)
        return {k: round(v / total, 3) for k, v in counts.items()}

    def to_card_fields(self) -> tuple[list[str], list[dict]]:
        """Return (concept_term_list, relation_dicts) suitable for PaperCard."""
        terms = [
            CONCEPT_REGISTRY[c].description
            for c in self.unique_concept_names()
            if c in CONCEPT_REGISTRY
        ]
        rels = [
            {
                "source": CONCEPT_REGISTRY[r.source].description if r.source in CONCEPT_REGISTRY else r.source,
                "target": CONCEPT_REGISTRY[r.target].description if r.target in CONCEPT_REGISTRY else r.target,
                "relation": r.relation,
                "weight": r.weight,
            }
            for r in self.relations
            if r.relation != "co_occurs"  # omit noisy co-occurrence from card
        ]
        return terms, rels


# ---------------------------------------------------------------------------
# Concept mention detection
# ---------------------------------------------------------------------------

def find_concept_mentions(text: str) -> list[ConceptMention]:
    """Scan lower-cased text for concept aliases; longest match wins."""
    low = text.lower()
    # Sort longest first so "matrix product state" beats "mps" at same position
    candidates = sorted(ALIAS_TO_CANONICAL.keys(), key=len, reverse=True)
    covered: set[tuple[int, int]] = set()
    mentions: list[ConceptMention] = []

    for alias in candidates:
        start = 0
        while True:
            pos = low.find(alias, start)
            if pos == -1:
                break
            end = pos + len(alias)

            # Short aliases require word boundaries
            if alias in SHORT_ALIASES:
                before_ok = pos == 0 or not low[pos - 1].isalnum()
                after_ok = end >= len(low) or not low[end].isalnum()
                if not (before_ok and after_ok):
                    start = pos + 1
                    continue

            # Skip if this span is already covered by a longer match
            if any(s <= pos and end <= e for s, e in covered):
                start = pos + 1
                continue

            canon = ALIAS_TO_CANONICAL[alias]
            meta = CONCEPT_REGISTRY[canon]
            mentions.append(ConceptMention(
                canonical=canon,
                concept_type=meta.type,
                alias_found=alias,
                start=pos,
                end=end,
            ))
            covered.add((pos, end))
            start = end

    mentions.sort(key=lambda m: m.start)
    return mentions


# ---------------------------------------------------------------------------
# Relation extraction (sentence-level)
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _sentence_relations(sentence: str, mentions: list[ConceptMention]) -> list[ConceptRelation]:
    """Extract typed (or co-occurrence) relations from mentions in one sentence."""
    if len(mentions) < 2:
        return []

    low = sentence.lower()
    evidence = sentence[:200]
    relations: list[ConceptRelation] = []

    # Collect all relation patterns that fire in this sentence
    fired: list[tuple[re.Match, str]] = []
    for pattern, rel_type in _COMPILED_PATTERNS:
        m = pattern.search(low)
        if m:
            fired.append((m, rel_type))

    if not fired:
        # Co-occurrence: all unique pairs
        for i, a in enumerate(mentions):
            for b in mentions[i + 1:]:
                if a.canonical != b.canonical:
                    relations.append(ConceptRelation(
                        a.canonical, b.canonical, "co_occurs",
                        RELATION_WEIGHT["co_occurs"], evidence,
                    ))
        return relations

    # Typed: for each fired pattern, find source (before verb) and target (after verb)
    seen: set[tuple[str, str, str]] = set()
    for match, rel_type in fired:
        verb_start = match.start()
        verb_end = match.end()
        before = [m for m in mentions if m.end <= verb_start]
        after = [m for m in mentions if m.start >= verb_end]

        if before and after:
            src = before[-1].canonical
            tgt = after[0].canonical
        elif len(mentions) >= 2:
            src, tgt = mentions[0].canonical, mentions[1].canonical
        else:
            continue

        if src == tgt:
            continue
        key = (src, tgt, rel_type)
        if key in seen:
            continue
        seen.add(key)
        relations.append(ConceptRelation(
            src, tgt, rel_type,
            RELATION_WEIGHT.get(rel_type, 1.0), evidence,
        ))

    return relations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_from_paper(
    title: str,
    abstract: str,
    full_text: str | None = None,
) -> ConceptExtractionResult:
    """Extract concepts and typed relations from a paper.

    Uses title + abstract + up to 2 000 chars of full text (no PDF into model).
    """
    blob = f"{title}. {abstract}"
    if full_text:
        blob += " " + full_text[:2000]

    all_mentions = find_concept_mentions(blob)

    # Per-sentence relation extraction
    sentences = _split_sentences(blob)
    all_relations: list[ConceptRelation] = []
    for sent in sentences:
        sent_mentions = find_concept_mentions(sent)
        all_relations.extend(_sentence_relations(sent, sent_mentions))

    # Deduplicate: keep highest-weight instance of each (src, tgt, rel) triple
    best: dict[tuple[str, str, str], ConceptRelation] = {}
    for r in all_relations:
        key = (r.source, r.target, r.relation)
        if key not in best or r.weight > best[key].weight:
            best[key] = r

    return ConceptExtractionResult(
        concepts=all_mentions,
        relations=list(best.values()),
    )
