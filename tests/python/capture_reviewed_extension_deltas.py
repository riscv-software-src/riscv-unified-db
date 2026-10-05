# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Explicit development capture of classified deltas, never an automatic test update."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

from extension_documents_helpers import formatter_lines, repaired_anchor_expectation
from test_extension_fidelity import CASES, FIXTURES, digest, selectors_for


def functions(lines):
    text = "\n".join(lines)
    sections = re.split(r"(?m)^\[#udb-function-", text)[1:]
    return {section.partition("]")[0]: section for section in sections}


def corrected_tuple(text):
    for names, call in (
        ("norm_exp, frac", "softfloat_normSubnormalF16Sig"),
        ("match_result, cfg", "pmp_match"),
    ):
        pattern = (
            r"\("
            + names
            + r" = (xref:#udb-function-"
            + call
            + r"\["
            + call
            + r"\]pass:\[\(\][^\n]+)\);"
        )
        text = re.sub(pattern, "(" + names + r") = \1;", text)
    return text


def capture(directory: Path):
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    result = {}
    for case_id in CASES:
        case = next(case for case in manifest["outcomes"] if case["id"] == case_id)
        raw = (FIXTURES / case["artifact"]).read_text()
        names = [selector.partition("@")[0] for selector in selectors_for(case)]
        original = formatter_lines(repaired_anchor_expectation(raw, names))
        actual = formatter_lines((directory / (case_id + ".adoc")).read_text())
        old_functions, new_functions = functions(original), functions(actual)
        assert old_functions.keys() <= new_functions.keys()
        for name, old in old_functions.items():
            assert corrected_tuple(old) == new_functions[name], name
        boundary = original.index("== IDL Functions")
        edits = []
        matcher = difflib.SequenceMatcher(a=original, b=actual, autojunk=False)
        for kind, start, end, new_start, new_end in matcher.get_opcodes():
            if kind == "equal":
                continue
            before, after = original[start:end], actual[new_start:new_end]
            if len(before) == len(after) == 1 and corrected_tuple(before[0]) == after[0]:
                classification = "native-tuple-assignment-correction"
            elif start > boundary:
                classification = "source-visible-function-declarations"
            elif not before and after[0] == "=== Parameters":
                classification = "normative-global-parameters"
            elif not before and after[0] == "=== Requirements":
                classification = "normative-version-requirements"
            elif (
                case_id == "zicsr-full"
                and len(before) == len(after) == 1
                and (
                    before[0] == "h^ Length         ^ -bit"
                    or ('"bits":64' in before[0] and '"bits":32' in after[0])
                )
            ):
                classification = "native-fixed-rv32-csr-correction"
            elif (
                case_id == "xqci-original-script"
                and len(before) == len(after) == 1
                and (before[0].startswith("++(") and after[0].startswith("++("))
            ):
                classification = "complete-implied-condition"
            else:
                raise AssertionError((case_id, start, before[:3], after[:3]))
            edits.append(
                {
                    "classification": classification,
                    "native_line": start + 1,
                    "context_before": original[max(0, start - 3) : start],
                    "before": before,
                    "after": after,
                    "context_after": original[end : end + 3],
                }
            )
        result[case_id] = {
            "native_with_anchor_repairs_sha256": digest(original),
            "reviewed_complete_sha256": digest(actual),
            "additional_function_declarations": sorted(new_functions.keys() - old_functions.keys()),
            "edits": edits,
        }
        print(
            case_id,
            len(edits),
            "explicit edits;",
            len(new_functions) - len(old_functions),
            "additional declarations",
        )
    (FIXTURES / "reviewed-deltas.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="already audited complete Python artifacts")
    capture(parser.parse_args().directory)
