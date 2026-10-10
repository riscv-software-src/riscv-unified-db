# SPDX-FileCopyrightText: 2024-2025 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Integrity checks for the parameter-extraction evaluation fixtures.

The fixtures are a frozen set of specification excerpts paired with the outcome
a parameter-extraction procedure should reach on each. Cases come in three kinds:

  * positives yield a parameter that UnifiedDB already models
  * negatives yield nothing, and are passages where a plausible rule produces a
    parameter that should not exist
  * candidates are surfaced and then classified out. They yield no parameter,
    but dropping them silently during extraction hides the decision from review

This file checks the *fixtures*, not a model. It is deterministic, needs no API
key and no network, and exists so the set cannot rot unnoticed:

  * every case is well formed and states its expectation
  * every positive is anchored to a parameter file that still exists upstream,
    so an upstream rename breaks the test instead of silently invalidating it
  * every negative expects nothing extracted and records the risk it guards
  * the set exercises both directions: a rule can fire where it should not, and
    it can fail to fire where it should

Run:

    ./bin/python -m pytest tools/python/param-extraction-eval -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
CASES = HERE / "cases"
REPO = HERE.parents[2]
PARAM_DIR = REPO / "spec" / "std" / "isa" / "param"


def _cases(kind: str) -> list[Path]:
    d = CASES / kind
    return sorted(p for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


POSITIVES = _cases("positives")
NEGATIVES = _cases("negatives")
CANDIDATES = _cases("candidates")
ALL_CASES = POSITIVES + NEGATIVES + CANDIDATES


def test_the_set_is_the_expected_shape():
    """An emptied fixture directory should fail loudly rather than pass vacuously."""
    assert len(POSITIVES) == 6, f"expected 6 positives, found {len(POSITIVES)}"
    assert len(NEGATIVES) == 4, f"expected 4 negatives, found {len(NEGATIVES)}"
    assert len(CANDIDATES) == 1, f"expected 1 candidate, found {len(CANDIDATES)}"


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda p: p.name)
def test_case_is_well_formed(case: Path):
    source = case / "source.txt"
    expected = case / "expected.yaml"
    assert source.is_file(), f"{case.name}: missing source.txt"
    assert expected.is_file(), f"{case.name}: missing expected.yaml"
    assert source.read_text(encoding="utf-8").strip(), f"{case.name}: source.txt is empty"

    exp = _load(expected)
    assert exp.get("id") == case.name, f"{case.name}: id does not match the directory name"
    assert isinstance(exp.get("expect_extract"), bool), (
        f"{case.name}: expect_extract must be present and boolean"
    )


@pytest.mark.parametrize("case", NEGATIVES, ids=lambda p: p.name)
def test_negative_expects_nothing_and_states_its_risk(case: Path):
    """A negative that expects a parameter, or does not say what it guards, is not useful."""
    exp = _load(case / "expected.yaml")
    assert exp["expect_extract"] is False, f"{case.name}: negative must set expect_extract false"
    assert exp.get("expect_params") == 0, f"{case.name}: negative must expect 0 parameters"
    assert exp.get("kind"), f"{case.name}: negative must name the failure kind"
    assert exp.get("skill_risk"), f"{case.name}: negative must state the risk it guards against"


@pytest.mark.parametrize("case", POSITIVES, ids=lambda p: p.name)
def test_positive_is_anchored_to_a_real_parameter(case: Path):
    """Positives point at real UDB parameters, so upstream renames surface here."""
    exp = _load(case / "expected.yaml")
    assert exp["expect_extract"] is True, f"{case.name}: positive must set expect_extract true"

    name = exp.get("gold_name")
    assert name, f"{case.name}: positive must declare gold_name"
    assert (PARAM_DIR / f"{name}.yaml").is_file(), (
        f"{case.name}: gold parameter '{name}' has no file under spec/std/isa/param. "
        "Either it was renamed upstream or this fixture is stale."
    )

    declared = exp.get("expect_udb_file")
    assert declared, f"{case.name}: positive must declare expect_udb_file"
    assert (REPO / declared).is_file(), (
        f"{case.name}: expect_udb_file '{declared}' does not exist in this checkout"
    )
    assert declared.endswith(f"{name}.yaml"), (
        f"{case.name}: expect_udb_file '{declared}' disagrees with gold_name '{name}'"
    )


@pytest.mark.parametrize("case", POSITIVES, ids=lambda p: p.name)
def test_positive_gold_file_agrees_with_expectation(case: Path):
    """The bundled gold.yaml must not drift from what the case claims."""
    gold_file = case / "gold.yaml"
    assert gold_file.is_file(), f"{case.name}: positive is missing gold.yaml"
    gold = _load(gold_file)
    exp = _load(case / "expected.yaml")
    assert gold.get("name") == exp.get("gold_name"), (
        f"{case.name}: gold.yaml name '{gold.get('name')}' "
        f"disagrees with expected.yaml gold_name '{exp.get('gold_name')}'"
    )
    if "class" in exp and "class" in gold:
        assert gold["class"] == exp["class"], f"{case.name}: class disagrees between files"


@pytest.mark.parametrize("case", CANDIDATES, ids=lambda p: p.name)
def test_candidate_is_surfaced_then_classified_out(case: Path):
    """A candidate is neither a positive nor a negative.

    It must be surfaced, because a procedure that drops it during extraction
    hides the decision from whoever reviews the output, and it must yield no
    parameter, because none exists to model.
    """
    exp = _load(case / "expected.yaml")
    assert exp["expect_extract"] is True, f"{case.name}: candidate must set expect_extract true"
    assert exp.get("expect_params") == 0, f"{case.name}: candidate must expect 0 parameters"
    assert exp.get("kind"), f"{case.name}: candidate must name the kind"
    assert exp.get("skill_risk"), f"{case.name}: candidate must state what it guards against"


def test_warl_fixed_legal_set_case_is_present():
    """The distinction the set exists to protect.

    A field can carry the word WARL while its legal value set is fixed by the
    ISA, and no parameter follows. It is filed as a candidate rather than a
    negative: the outcome is no parameter either way, but the procedure should
    record that decision instead of never raising the case at all.

    The WARL positive is what stops the rule being tightened into uselessness.
    """
    assert "CAND_WARL_FIXED_LEGAL_SET" in {c.name for c in CANDIDATES}, (
        "the WARL-with-ISA-fixed-legal-set case is missing; "
        "without it the set no longer guards its central distinction"
    )
    case = CASES / "candidates" / "CAND_WARL_FIXED_LEGAL_SET"
    assert _load(case / "expected.yaml")["expect_params"] == 0
    assert "WARL" in (case / "source.txt").read_text(encoding="utf-8"), (
        "the WARL candidate should contain the WARL keyword, or it tests nothing"
    )

    positive_warl = [
        c for c in POSITIVES if _load(c / "expected.yaml").get("warl_true_parameter") is True
    ]
    assert positive_warl, (
        "a WARL positive must exist alongside it, otherwise a rule that rejects "
        "every WARL field would pass the set"
    )


def test_the_set_exercises_both_directions():
    """Over-firing is only half the problem.

    A rule keyed on the WARL and WLRL tokens misses fields whose legal values
    depend on the implementation without either token appearing. Cases marked
    recall_case carry no such token, so a set without them measures precision
    only.
    """
    recall = [c for c in ALL_CASES if _load(c / "expected.yaml").get("recall_case") is True]
    assert len(recall) >= 2, (
        f"expected at least 2 recall cases, found {len(recall)}; "
        "without them the set tests only whether a rule fires too often"
    )
    for case in recall:
        text = (case / "source.txt").read_text(encoding="utf-8")
        assert "WARL" not in text and "WLRL" not in text, (
            f"{case.name}: a recall case must not contain a WARL or WLRL token, "
            "otherwise a token-keyed rule would find it and it tests nothing"
        )


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda p: p.name)
def test_case_id_prefix_matches_its_directory(case: Path):
    exp = _load(case / "expected.yaml")
    prefix = {"positives": "POS_", "negatives": "NEG_", "candidates": "CAND_"}[case.parent.name]
    assert exp["id"].startswith(prefix), f"{case.name}: id should start with {prefix}"
