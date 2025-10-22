import pytest
import os, sys

# Make sure Python can find backends/generators/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backends.generators.schema_validator import validate_entry


def test_success_top_level():
    entry = {"address": "0x123", "type": "rw"}
    validate_entry(entry, ["address", "type"])  # should not raise


def test_success_nested():
    entry = {"encoding": {"match": "0x1", "mask": "0x2"}}
    validate_entry(entry, ["encoding.match", "encoding.mask"])  # should not raise


def test_missing_top_level():
    entry = {"address": "0x123"}
    with pytest.raises(AssertionError):
        validate_entry(entry, ["address", "type"])


def test_missing_nested():
    entry = {"encoding": {"match": "0x1"}}
    with pytest.raises(AssertionError):
        validate_entry(entry, ["encoding.match", "encoding.mask"])
