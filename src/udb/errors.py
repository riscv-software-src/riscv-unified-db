# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Exceptions raised by the raw UDB data API."""


class UdbError(Exception):
    """Base class for UDB errors."""


class DataError(UdbError):
    """A UDB YAML document is malformed or internally inconsistent."""


class ResolutionError(DataError):
    """Inheritance or overlay resolution failed."""


class SerializationError(DataError):
    """UDB data cannot be serialized deterministically or portably."""


class AuthoringError(UdbError):
    """Generated output ownership or filesystem safety is invalid."""


class LayoutError(UdbError):
    """A source layout cannot be rendered or written safely."""


class UnknownKindError(UdbError, KeyError):
    """The requested object kind is not present in the database."""


class ObjectNotFoundError(UdbError, KeyError):
    """No object with the requested kind and name exists."""
