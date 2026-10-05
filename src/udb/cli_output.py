# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-FileCopyrightText: Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""UTF-8 output shared by source-generating command-line interfaces."""

import sys
from pathlib import Path

from .errors import UdbError


def write_generated_source(
    text: str, output: Path | None, *, artifact: str, create_parents: bool = False
) -> None:
    destination = "stdout" if output is None else str(output)
    try:
        encoded = text.encode("utf-8")
        if output is None:
            stream = getattr(sys.stdout, "buffer", None)
            if stream is None:
                raise OSError("stdout has no binary stream for UTF-8 output")
            # Raw writes avoid locale/newline translation and buffered
            # retries at shutdown after a broken pipe.
            stream = getattr(stream, "raw", stream)
            remaining = memoryview(encoded)
            while remaining:
                written = stream.write(remaining)
                if written is None or written <= 0:
                    raise OSError(f"stdout did not accept the complete {artifact}")
                remaining = remaining[written:]
            stream.flush()
        else:
            if create_parents:
                output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(encoded)
    except (OSError, UnicodeError) as error:
        raise UdbError(f"{destination}: cannot write {artifact}: {error}") from error
