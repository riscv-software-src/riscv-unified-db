# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-FileCopyrightText: Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""UTF-8, atomic file, and drift output shared by installed commands."""

import os
import sys
import tempfile
from pathlib import Path

from .errors import UdbError


def _write_stream(payload: bytes, *, artifact: str) -> None:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        raise OSError("stdout has no binary stream for UTF-8 output")
    stream = getattr(stream, "raw", stream)
    remaining = memoryview(payload)
    while remaining:
        written = stream.write(remaining)
        if written is None or written <= 0:
            raise OSError(f"stdout did not accept the complete {artifact}")
        remaining = remaining[written:]
    stream.flush()


def _write_atomic(path: Path, payload: bytes, *, create_parents: bool) -> None:
    temporary: Path | None = None
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_generated_source(
    text: str,
    output: Path | None,
    *,
    artifact: str,
    create_parents: bool = False,
    check: bool = False,
) -> bool:
    stdout = output is None or output == Path("-")
    if check and stdout:
        raise UdbError(f"--check for {artifact} requires a non-stdout output")
    destination = "stdout" if stdout else str(output)
    try:
        encoded = text.encode("utf-8")
        if stdout:
            _write_stream(encoded, artifact=artifact)
        elif check:
            assert output is not None
            if not output.is_file() or output.read_bytes() != encoded:
                print(output)
                return True
        else:
            assert output is not None
            _write_atomic(output, encoded, create_parents=create_parents)
    except (OSError, UnicodeError) as error:
        raise UdbError(f"{destination}: cannot write {artifact}: {error}") from error
    return False
