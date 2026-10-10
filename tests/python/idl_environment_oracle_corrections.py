# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Account only for Ruby's weaker knowledge of catalog-impossible versions."""

from copy import deepcopy
from typing import Any

from udb.database import ResolvedDatabase
from udb.versions import VersionRequirement


def corrected_environment_expectation(
    database: ResolvedDatabase, frozen: dict[str, Any]
) -> dict[str, Any]:
    expected = deepcopy(frozen)
    for name, observation in expected["extensions"].items():
        versions = database.extension(name).versions
        for requirement, value in observation["implemented_version"].items():
            query = VersionRequirement.parse(requirement)
            if value is None and not any(query.matches(version.version) for version in versions):
                observation["implemented_version"][requirement] = False
    return expected
