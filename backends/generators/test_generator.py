import pytest
from generator import condition_holds

ZBB = {"extension": {"name": "Zbb"}}
ZBB_RV64 = {"allOf": [{"xlen": 64}, ZBB]}
# zext.h: Zbb and not Zbkb
ZEXT_H = {"extension": {"allOf": [{"name": "Zbb"}, {"not": {"name": "Zbkb"}}]}}
# c.ld-style: (RV64 and Zca) or Zclsd
C_LD = {
    "anyOf": [
        {"allOf": [{"xlen": 64}, {"extension": {"name": "Zca"}}]},
        {"extension": {"name": "Zclsd"}},
    ]
}


@pytest.mark.parametrize(
    "condition,enabled,arch,expected",
    [
        # Single extension via the {extension: {name}} form used throughout UDB
        (ZBB, ["Zbb"], "RV64", True),
        (ZBB, ["I"], "RV64", False),
        ({"extension": {"name": "I", "version": ">= 2.0"}}, ["I"], "RV64", True),
        # {allOf: [xlen, extension]}: both the extension and the target arch must match
        (ZBB_RV64, ["Zbb"], "RV64", True),
        (ZBB_RV64, ["Zbb"], "BOTH", True),
        (ZBB_RV64, ["Zbb"], "RV32", False),
        (ZBB_RV64, ["I"], "RV64", False),
        ({"allOf": [{"xlen": 32}, ZBB]}, ["Zbb"], "RV64", False),
        ({"allOf": [{"xlen": 32}, ZBB]}, ["Zbb"], "RV32", True),
        # A bare xlen condition
        ({"xlen": 64}, [], "RV32", False),
        ({"xlen": 64}, [], "RV64", True),
        # {allOf: [extension, param]}: the param term is neutral
        (
            {"allOf": [{"extension": {"name": "I"}}, {"param": {"name": "MXLEN", "equal": 64}}]},
            ["I"],
            "RV64",
            True,
        ),
        # extension.anyOf / oneOf: any alternative enables the instruction
        ({"extension": {"anyOf": [{"name": "I"}, {"name": "Zilsd"}]}}, ["Zilsd"], "RV64", True),
        ({"extension": {"anyOf": [{"name": "I"}, {"name": "Zilsd"}]}}, ["M"], "RV64", False),
        ({"extension": {"oneOf": [{"name": "Zfh"}, {"name": "Zhinx"}]}}, ["Zhinx"], "RV64", True),
        ({"extension": {"oneOf": [{"name": "Zfh"}, {"name": "Zhinx"}]}}, ["C"], "RV64", False),
        # extension.allOf: every named extension must be enabled
        ({"extension": {"allOf": [{"name": "A"}, {"name": "B"}]}}, ["A", "B"], "RV64", True),
        ({"extension": {"allOf": [{"name": "A"}, {"name": "B"}]}}, ["A"], "RV64", False),
        # extension.allOf with a "not" term
        (ZEXT_H, ["Zbb"], "RV64", True),
        (ZEXT_H, ["Zbb", "Zbkb"], "RV64", False),
        # extension with an anyOf alongside a null name (custom data form)
        (
            {"extension": {"name": None, "anyOf": [{"name": "Zcmt"}, {"name": "Xqccmt"}]}},
            ["Xqccmt"],
            "RV64",
            True,
        ),
        # top-level anyOf with a nested allOf alternative
        (C_LD, ["Zclsd"], "RV32", True),
        (C_LD, ["Zca"], "RV64", True),
        (C_LD, ["Zca"], "RV32", False),
        (C_LD, ["I"], "RV64", False),
        # --include-all (enabled=None): extensions are ignored but xlen is still enforced
        (ZBB, None, "RV64", True),
        (ZEXT_H, None, "RV64", True),
        (ZBB_RV64, None, "RV64", True),
        (ZBB_RV64, None, "RV32", False),
        (C_LD, None, "RV32", True),
    ],
)
def test_condition_holds(condition, enabled, arch, expected):
    assert condition_holds(condition, enabled, arch) is expected
