"""Tests for the first-principles dataset exporter."""

from __future__ import annotations

import json

from researcher_mcp.indexing import dataset_export, pipeline
from researcher_mcp.storage import repository as repo
from researcher_mcp.storage.models import Paper

_ENVELOPE_KEYS = {"id", "type", "domain", "text", "structured", "provenance", "meta"}


def _build_corpus() -> None:
    papers = [
        Paper(arxiv_id="2502.0001", title="VQE improves on DMRG",
              abstract="The variational quantum eigensolver improves on DMRG. "
                       "It is applied to the Heisenberg model."),
        Paper(arxiv_id="2502.0002", title="Comparing VQE and DMRG",
              abstract="The variational quantum eigensolver is compared with DMRG on the Ising model."),
        Paper(arxiv_id="2502.0003", title="DMRG for chemistry",
              abstract="DMRG is applied to electronic structure and the Hubbard model."),
    ]
    for p in papers:
        repo.upsert_paper(p)
    pipeline.rebuild_index(reset=True)


def test_triples_have_envelope_and_provenance():
    _build_corpus()
    records = dataset_export.build_triples(min_confidence=0.5)
    assert records
    for r in records:
        assert _ENVELOPE_KEYS <= set(r)
        assert r["type"] == "triple"
        assert r["provenance"]["paper_ids"]
        assert r["meta"]["relation"] != "co_occurs"  # excluded by default
        assert r["provenance"]["evidence"][0]["text"]


def test_reasoning_chains_are_evidenced_and_multihop():
    _build_corpus()
    chains = dataset_export.build_reasoning_chains(min_confidence=0.5)
    for c in chains:
        assert c["type"] == "reasoning_chain"
        assert c["meta"]["hops"] >= 2
        assert len(set(c["structured"]["nodes"])) == len(c["structured"]["nodes"])  # no repeats
        for step in c["structured"]["steps"]:
            assert step["evidence"]  # every hop must cite evidence


def test_qa_pairs_are_grounded():
    _build_corpus()
    qa = dataset_export.build_qa_pairs(min_confidence=0.5)
    assert qa
    for r in qa:
        assert r["type"] == "qa"
        assert r["text"].startswith("Q:")
        assert r["provenance"]["paper_ids"]


def test_contrastive_finds_disagreement():
    _build_corpus()  # paper1 says VQE improves_on DMRG; paper2 says compared_to
    contrast = dataset_export.build_contrastive()
    assert contrast, "expected at least one contrastive pair"
    rec = contrast[0]
    assert rec["type"] == "contrastive"
    assert len(rec["meta"]["relation_types"]) >= 2
    assert len(rec["provenance"]["paper_ids"]) >= 2


def test_export_writes_jsonl_and_manifest(tmp_path):
    _build_corpus()
    out = dataset_export.export_dataset(out_dir=tmp_path, min_confidence=0.5)
    assert out["total"] >= 1
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert "files" in manifest
    # Every emitted file is valid JSONL.
    for fmt, info in out["files"].items():
        lines = [ln for ln in open(info["path"]) if ln.strip()]
        assert len(lines) == info["count"]
        for ln in lines:
            json.loads(ln)  # must parse


def test_min_confidence_filters_triples():
    _build_corpus()
    lo = dataset_export.build_triples(min_confidence=0.0, include_co_occurs=True)
    hi = dataset_export.build_triples(min_confidence=0.99)
    assert len(lo) >= len(hi)
