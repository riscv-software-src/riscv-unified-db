# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Python access to the RISC-V Unified Database."""

from .database import (
    Csr,
    Database,
    DatabaseObject,
    Extension,
    Instruction,
    Profile,
    ResolvedDatabase,
)
from .errors import (
    DataError,
    ObjectNotFoundError,
    ResolutionError,
    SerializationError,
    UdbError,
    UnknownKindError,
)
from .resolver import YamlResolver, merge_patch
from .schema import SchemaError, SchemaStore
from .serialization import (
    SCHEMAS_BASE_URL,
    dumps_json,
    dumps_yaml,
    write_config,
    write_resolved_database,
    write_resolved_schemas,
)

__all__ = [
    "SCHEMAS_BASE_URL",
    "Csr",
    "DataError",
    "Database",
    "DatabaseObject",
    "Extension",
    "Instruction",
    "ObjectNotFoundError",
    "Profile",
    "ResolutionError",
    "ResolvedDatabase",
    "SchemaError",
    "SchemaStore",
    "SerializationError",
    "UdbError",
    "UnknownKindError",
    "YamlResolver",
    "dumps_json",
    "dumps_yaml",
    "merge_patch",
    "write_config",
    "write_resolved_database",
    "write_resolved_schemas",
]
