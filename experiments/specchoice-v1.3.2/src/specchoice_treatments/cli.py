# SPDX-License-Identifier: BSD-3-Clause-Clear
"""The sole offline CLI for test-only retrieval-contract verification."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes

from .retrieval import (
    RetrievalContractError,
    _canonical_read,
    build_retrieval_report_v1,
    load_prompt_manifest_v1,
    load_retrieval_contract_v1,
    validate_test_only_corpus_v1,
    validate_test_only_target_v1,
)

_EXPERIMENT_ROOT = Path(__file__).resolve().parents[2]


def _verify_retrieval_contract(args: argparse.Namespace) -> int:
    target, _ = _canonical_read(_EXPERIMENT_ROOT, args.target, "RETRIEVAL_CLI_INPUT_INVALID")
    corpus, _ = _canonical_read(_EXPERIMENT_ROOT, args.corpus, "RETRIEVAL_CLI_INPUT_INVALID")
    config = load_retrieval_contract_v1(_EXPERIMENT_ROOT, args.config)
    validate_test_only_target_v1(target)
    validate_test_only_corpus_v1(corpus)
    prompt_manifest = load_prompt_manifest_v1(
        _EXPERIMENT_ROOT,
        args.prompt_manifest,
        target=target,
        corpus=corpus,
    )
    sys.stdout.buffer.write(
        canonical_json_bytes(
            build_retrieval_report_v1(
                target=target,
                corpus=corpus,
                config=config,
                prompt_manifest=prompt_manifest,
            )
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build an intentionally singleton command surface."""
    parser = argparse.ArgumentParser(prog="specchoice-treatments")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("verify-retrieval-contract")
    command.add_argument("--target", required=True)
    command.add_argument("--corpus", required=True)
    command.add_argument("--config", required=True)
    command.add_argument("--prompt-manifest", required=True)
    command.set_defaults(handler=_verify_retrieval_contract)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Write canonical stdout or a stable error and exit 2."""
    try:
        args = build_parser().parse_args(argv)
        return int(args.handler(args))
    except (RetrievalContractError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except SystemExit as error:
        return int(error.code)


if __name__ == "__main__":
    raise SystemExit(main())
