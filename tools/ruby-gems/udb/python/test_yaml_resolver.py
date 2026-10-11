# SPDX-FileCopyrightText: Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-FileCopyrightText: 2024-2025 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import pytest
import yaml_resolver
from yaml_resolver import merge_file, resolve


@pytest.fixture(autouse=True)
def _clear_resolve_cache():
    """resolve() memoizes by relative path, so isolate each test."""
    yaml_resolver.resolved_objs.clear()


def _make_arch(tmp_path, inherits_target):
    arch_root = tmp_path / "arch"
    (arch_root / "ext").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secrets.yaml").write_text('name: secrets\nsecret: "s3cret"\n')
    (arch_root / "ext" / "Evil.yaml").write_text(f'name: Evil\n$inherits: "{inherits_target}"\n')
    return arch_root


def test_inherits_rejects_relative_path_escaping_arch_root(tmp_path):
    arch_root = _make_arch(tmp_path, "../outside/secrets.yaml#")

    with pytest.raises(ValueError, match="escapes"):
        resolve("ext/Evil.yaml", arch_root, False, False)


def test_inherits_rejects_absolute_path(tmp_path):
    arch_root = _make_arch(tmp_path, f"{tmp_path / 'outside' / 'secrets.yaml'}#")

    with pytest.raises(ValueError, match="escapes"):
        resolve("ext/Evil.yaml", arch_root, False, False)


def test_inherits_still_resolves_targets_inside_arch_root(tmp_path):
    arch_root = tmp_path / "arch"
    (arch_root / "ext").mkdir(parents=True)
    (arch_root / "ext" / "Base.yaml").write_text("name: Base\nfoo: 1\n")
    (arch_root / "ext" / "Child.yaml").write_text(
        'name: Child\n$inherits: "ext/Base.yaml#"\nbar: 2\n'
    )

    resolved = resolve("ext/Child.yaml", arch_root, False, False)

    assert resolved["foo"] == 1
    assert resolved["bar"] == 2


def test_out_of_tree_overlay_inherits_across_the_merged_tree(tmp_path):
    """An `arch_overlay` may live outside the repo, but resolution never sees it: merging
    copies the overlay into the merged tree first, and only that tree is ever an arch root.
    This pins the ordering so the containment check can't be mistaken for an overlay break.
    """
    std_dir = tmp_path / "std"
    (std_dir / "ext").mkdir(parents=True)
    (std_dir / "ext" / "Base.yaml").write_text("name: Base\nfoo: 1\n")

    overlay_dir = tmp_path / "outside" / "overlay"
    (overlay_dir / "ext").mkdir(parents=True)
    (overlay_dir / "ext" / "MyExt.yaml").write_text(
        'name: MyExt\n$inherits: "ext/Base.yaml#"\nbar: 2\n'
    )

    merged_dir = tmp_path / "merged"
    (merged_dir / "ext").mkdir(parents=True)
    for rel_path in ("ext/Base.yaml", "ext/MyExt.yaml"):
        merge_file(rel_path, std_dir, overlay_dir, merged_dir)

    resolved = resolve("ext/MyExt.yaml", merged_dir, False, False)

    assert resolved["foo"] == 1, "overlay file could not inherit from the standard spec"
    assert resolved["bar"] == 2
