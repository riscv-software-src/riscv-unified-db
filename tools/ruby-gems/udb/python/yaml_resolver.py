# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import glob, os
import argparse
import shutil
import json
import sys

from pathlib import Path

from copy import deepcopy
from tqdm import tqdm
from ruamel.yaml import YAML
from mergedeep import merge, Strategy
from jsonschema import Draft7Validator, validators
from jsonschema.exceptions import best_match
from jsonschema.exceptions import ValidationError

from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

# cache of Schema validators
schemas = {}

udb_root = lambda d: (
    d if os.path.exists(os.path.join(d, "do")) else udb_root(os.path.dirname(d))
)
UDB_ROOT = (
    udb_root(os.path.dirname(os.path.realpath(__file__)))
    if os.getenv("UDB_ROOT") == None
    else os.getenv("UDB_ROOT")
)

SCHEMAS_PATH = Path(os.path.join(UDB_ROOT, "spec", "schemas"))


def retrieve_from_filesystem(uri: str):
    path = SCHEMAS_PATH / Path(uri)
    contents = json.loads(path.read_text())
    return Resource.from_contents(contents)


registry = Registry(retrieve=retrieve_from_filesystem)


# extend the validator to support default values
# https://python-jsonschema.readthedocs.io/en/stable/faq/#why-doesn-t-my-schema-s-default-property-set-the-default-on-my-instance
def extend_with_default(validator_class):
    """Extends the jsonschema validator to support default values.

    Parameters
    ----------
    validator_class : jsonschema.Draft7Validator
        The validator class to extend.

    Returns
    -------
    jsonschema.Draft7Validator
        The extended validator class that will fill in default values
    """

    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if not isinstance(subschema, dict):
                continue
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

        yield from validate_properties(
            validator,
            properties,
            instance,
            schema,
        )

    return validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


DefaultValidatingValidator = extend_with_default(Draft7Validator)

yaml = YAML(typ="rt")
yaml.default_flow_style = False
yaml.preserve_quotes = True


def _merge_patch(base: dict, patch: dict, path_so_far=[]) -> None:
    """merges patch into base according to JSON Merge Patch (RFC 7386)

    Parameters
    ----------
    base : dict
      The base object, which will be altered by the patch
    patch : dict
      The patch object
    path_so_far : list
      The current dict key path within patch
    """

    patch_obj = patch if len(path_so_far) == 0 else dig(patch, *path_so_far)
    for key, patch_value in patch_obj.items():
        if isinstance(patch_value, dict):
            # continue to dig
            _merge_patch(base, patch, (path_so_far + [key]))
        else:
            base_ptr = dig(base, *path_so_far)
            base_value = dig(base_ptr, key)
            if patch_value == None:
                # remove from base, if it exists
                if base_value != None:
                    base_ptr.pop(key)
            else:
                if base_ptr == None:
                    # add or overwrite value in base
                    base_ptr = base
                    for k in path_so_far:
                        if not k in base_ptr:
                            base_ptr[k] = {}
                        base_ptr = base_ptr[k]
                    base_ptr = dig(base, *path_so_far)
                base_ptr[key] = patch_value


def json_merge_patch(base_obj: dict, patch: dict) -> dict:
    """merges patch into base according to JSON Merge Patch (RFC 7386)

    Parameters
    ----------
    base : dict
      The base object, which will be altered by the patch
    patch : dict
      The patch object

    Returns
    -------
    dict
      base_obj, now with the patch applied
    """
    _merge_patch(base_obj, patch, [])
    return base_obj


def read_yaml(file_path: str | Path):
    """Read a YAML file from file_path and return the parsed content

    Parameters
    ----------
    file_path : str, Path
      Filesystem path to the YAML file

    Returns
    -------
    dict, list
      The object represented in the YAML file
    """
    with open(file_path) as file:
        data = yaml.load(file)
    return data


def write_yaml(file_path: str | Path, data):
    """Write data as YAML to file_path

    Parameters
    ----------
    file_path : str, Path
      Filesystem path to the YAML file
    data : dict, list
      The object to write as YAML
    """
    with open(file_path, "w") as file:
        yaml.dump(data, file)
        file.close()


def write_json(file_path: str | Path, data):
    """Write data as JSON to file_path

    Parameters
    ----------
    file_path : str, Path
      Filesystem path to the JSON file
    data : dict, list
      The object to write as JSON
    """
    with open(file_path, "w") as file:
        json.dump(data, file)
        file.close()


def dig(obj: dict, *keys):
    """Digs data out of dictionary obj

    Parameters
    ----------
    obj : dict
      A dictionary
    *keys
      A list of obj keys

    Returns
    -------
    Any
      The value of obj[keys[0]][keys[1]]...[keys[-1]]
    """
    if obj == None:
        return None

    if len(keys) == 0:
        return obj

    try:
        next_obj = obj[keys[0]]
        if len(keys) == 1:
            return next_obj
        else:
            if not isinstance(next_obj, dict):
                raise ValueError(f"Not a hash: {keys}")
            return dig(next_obj, *keys[1:])
    except KeyError:
        return None


resolved_objs = {}


def resolve(rel_path: str | Path, arch_root: str | Path, do_checks: bool) -> dict:
    """Resolve the file at arch_root/rel_path by expanding operators and applying defaults

    Parameters
    ----------
    rel_path : str, Path
      The relative path, from arch_root, to the file to resolve
    arch_root : str, Path
      The root of the architecture

    Returns
    -------
    dict
      The resolved object
    """
    if str(rel_path) in resolved_objs:
        return resolved_objs[str(rel_path)]
    else:
        unresolved_arch_data = read_yaml(os.path.join(arch_root, rel_path))
        if do_checks and (not "name" in unresolved_arch_data):
            print(
                f"ERROR: Missing 'name' key in {arch_root}/{rel_path}", file=sys.stderr
            )
            exit(1)
        fn_name = Path(rel_path).stem
        if do_checks and (fn_name != unresolved_arch_data["name"]):
            print(
                f"ERROR: 'name' key ({unresolved_arch_data['name']}) must match filename ({fn_name}) in {arch_root}/{rel_path}",
                file=sys.stderr,
            )
            exit(1)
        resolved_objs[str(rel_path)] = _resolve(
            unresolved_arch_data,
            [],
            rel_path,
            unresolved_arch_data,
            arch_root,
            do_checks,
        )
        return resolved_objs[str(rel_path)]


def _resolve(obj, obj_path, obj_file_path, doc_obj, arch_root, do_checks):
    if not (isinstance(obj, list) or isinstance(obj, dict)):
        return obj

    if isinstance(obj, list):
        obj = list(
            map(
                lambda o: _resolve(
                    o, obj_path, obj_file_path, doc_obj, arch_root, do_checks
                ),
                obj,
            )
        )
        return obj

    if "$inherits" in obj:
        # handle the inherits key first so that any override will have priority
        inherits_targets = (
            [obj["$inherits"]]
            if isinstance(obj["$inherits"], str)
            else obj["$inherits"]
        )
        obj["$child_of"] = obj["$inherits"]
        del obj["$inherits"]

        parent_obj = yaml.load("{}")

        for inherits_target in inherits_targets:
            ref_file_path = inherits_target.split("#")[0]
            ref_obj_path = inherits_target.split("#")[1].split("/")[1:]

            ref_obj = None
            if ref_file_path == "":
                ref_file_path = obj_file_path
                # this is a reference in the same document
                ref_obj = dig(doc_obj, *ref_obj_path)
                if ref_obj == None:
                    raise ValueError(f"{ref_obj_path} cannot be found in #{doc_obj}")
                ref_obj = _resolve(
                    ref_obj, ref_obj_path, ref_file_path, doc_obj, arch_root, do_checks
                )
            else:
                # this is a reference to another doc
                if not os.path.exists(os.path.join(arch_root, ref_file_path)):
                    raise ValueError(f"{ref_file_path} does not exist in {arch_root}/")

                ref_doc_obj = resolve(ref_file_path, arch_root, do_checks)
                ref_obj = dig(ref_doc_obj, *ref_obj_path)

                ref_obj = _resolve(
                    ref_obj,
                    ref_obj_path,
                    ref_file_path,
                    ref_doc_obj,
                    arch_root,
                    do_checks,
                )

            for key in ref_obj:
                if key == "$parent_of" or key == "$child_of":
                    continue  # we don't propagate $parent_of / $child_of
                if isinstance(parent_obj.get(key), dict):
                    merge(parent_obj[key], ref_obj[key], strategy=Strategy.REPLACE)
                else:
                    parent_obj[key] = deepcopy(ref_obj[key])

            if "$parent_of" in ref_obj:
                if isinstance(ref_obj["$parent_of"], list):
                    ref_obj["$parent_of"].append(
                        f"{obj_file_path}#/{'/'.join(obj_path)}"
                    )
                else:
                    ref_obj["$parent_of"] = [
                        ref_obj["$parent_of"],
                        f"{obj_file_path}#/{'/'.join(obj_path)}",
                    ]
            else:
                ref_obj["$parent_of"] = f"{obj_file_path}#/{'/'.join(obj_path)}"

        # now parent_obj is the child and obj is the parent
        # merge them
        keys = []
        for key in obj.keys():
            keys.append(key)
        for key in parent_obj.keys():
            if keys.count(key) == 0:
                keys.append(key)

        final_obj = yaml.load("{}")
        for key in keys:
            if not key in obj:
                final_obj[key] = parent_obj[key]
            elif not key in parent_obj:
                final_obj[key] = _resolve(
                    obj[key],
                    obj_path + [key],
                    obj_file_path,
                    doc_obj,
                    arch_root,
                    do_checks,
                )
            else:
                if isinstance(parent_obj[key], dict):
                    final_obj[key] = merge(
                        yaml.load("{}"),
                        parent_obj[key],
                        _resolve(
                            obj[key],
                            obj_path + [key],
                            obj_file_path,
                            doc_obj,
                            arch_root,
                            do_checks,
                        ),
                        strategy=Strategy.REPLACE,
                    )
                else:
                    final_obj[key] = _resolve(
                        obj[key],
                        obj_path + [key],
                        obj_file_path,
                        doc_obj,
                        arch_root,
                        do_checks,
                    )

        if "$remove" in final_obj:
            if isinstance(final_obj["$remove"], list):
                for key in final_obj["$remove"]:
                    if key in final_obj:
                        del final_obj[key]
            else:
                if final_obj["$remove"] in final_obj:
                    del final_obj[final_obj["$remove"]]
            del final_obj["$remove"]

        return final_obj
    else:
        for key in obj:
            obj[key] = _resolve(
                obj[key], obj_path + [key], obj_file_path, doc_obj, arch_root, do_checks
            )

        if "$remove" in obj:
            if isinstance(obj["$remove"], list):
                for key in obj["$remove"]:
                    if key in obj:
                        del obj[key]
            else:
                if obj["$remove"] in obj:
                    del obj[obj["$remove"]]
            del obj["$remove"]

        return obj


def merge_file(
    rel_path: str | Path,
    arch_dir: str | Path,
    overlay_dir: str | Path | None,
    merge_dir: str | Path,
) -> None:
    """pick the right file(s) to merge, and write the result to merge_dir

    Parameters
    ----------
    rel_path : str, Path
      Relative path, from arch_dir, to base file
    arch_dir : str, Path
      Absolute path to arch dir with base files
    overlay_dir : str, Path, None
      Absolute path to overlay dir with overlay files
    merge_dir : str, Path
      Absolute path to merge dir, where the merged file will be written
    """
    arch_path = overlay_path = None

    if arch_dir != None:
        arch_path = os.path.join(arch_dir, rel_path)
    if overlay_dir != None:
        overlay_path = os.path.join(overlay_dir, rel_path)
    merge_path = os.path.join(merge_dir, rel_path)
    if not os.path.exists(arch_path) and (
        overlay_path == None or not os.path.exists(overlay_path)
    ):
        # neither exist
        if not os.path.exists(merge_path):
            raise "Script error: no path exists"

        # remove the merged file
        os.remove(merge_path)
    elif overlay_path == None or not os.path.exists(overlay_path):
        if arch_path == None:
            raise "Must supply with arch_path or overlay_path"

        # no overlay, just copy arch
        if not os.path.exists(merge_path) or (
            os.path.getmtime(arch_path) > os.path.getmtime(merge_path)
        ):
            shutil.copyfile(os.path.join(arch_dir, rel_path), merge_path)
    elif not os.path.exists(arch_path):
        if overlay_path == None or not os.path.exists(overlay_path):
            raise "Must supply with arch_path or overlay_path"

        # no arch, just copy overlay
        if not os.path.exists(merge_path) or (
            os.path.getmtime(overlay_path) > os.path.getmtime(merge_path)
        ):
            shutil.copyfile(os.path.join(overlay_dir, rel_path), merge_path)
    else:
        # both exist, merge
        if (
            not os.path.exists(merge_path)
            or (os.path.getmtime(overlay_path) > os.path.getmtime(merge_path))
            or (os.path.getmtime(arch_path) > os.path.getmtime(merge_path))
        ):
            arch_obj = read_yaml(os.path.join(arch_dir, rel_path))
            overlay_obj = read_yaml(os.path.join(overlay_dir, rel_path))

            write_yaml(
                os.path.join(merge_dir, rel_path),
                json_merge_patch(arch_obj, overlay_obj),
            )


class SchemaNotFoundException(Exception):
    pass


def _get_schema(uri):
    rel_path = uri.split("#")[0]

    if rel_path in schemas:
        return schemas[rel_path]

    abs_path = os.path.join(SCHEMAS_PATH, rel_path)
    if not os.path.exists(abs_path):
        raise SchemaNotFoundException(f"Schema not found: {uri}")

    # Open the JSON file
    with open(abs_path) as f:
        # Load the JSON data into a Python dictionary
        schema_obj = json.load(f)
        f.close()

    schemas[rel_path] = DefaultValidatingValidator(schema_obj, registry=registry)
    return schemas[rel_path]


def resolve_file(
    rel_path: str | Path,
    arch_dir: str | Path,
    resolved_dir: str | Path,
    do_checks: bool,
):
    """Read object at arch_dir/rel_path, resolve it, and write it as YAML to resolved_dir/rel_path

    Parameters
    ----------
    rel_path : str | Path
      Path to file relative to arch_dir
    arch_dir : str | Path
      Absolute path to arch directory
    resolved_dir : str | Path
      Directory to write the resolved file to
    """
    arch_path = os.path.join(arch_dir, rel_path)
    resolved_path = os.path.join(resolved_dir, rel_path)
    if not os.path.exists(arch_path):
        if os.path.exists(resolved_path):
            os.remove(resolved_path)
    elif (
        not os.path.exists(resolved_path)
        or (os.path.getmtime(arch_path) > os.path.getmtime(resolved_path))
        or (os.path.getmtime(__file__) > os.path.getmtime(resolved_path))
    ):
        if os.path.exists(resolved_path):
            os.remove(resolved_path)
        resolved_obj = resolve(rel_path, args.arch_dir, do_checks)
        resolved_obj["$source"] = os.path.join(args.arch_dir, rel_path)

        # since already-resolved objects may be updated later with inheritance breadcrumbs ($parent_of),
        # we can't write the file yet.


def write_resolved_file_and_validate(
    rel_path: str | Path,
    resolved_dir: str | Path,
    do_checks: bool,
):
    resolved_path = os.path.join(resolved_dir, rel_path)
    resolved_obj = resolve(rel_path, args.arch_dir, do_checks)
    resolved_obj["$source"] = os.path.join(args.arch_dir, rel_path)
    write_yaml(resolved_path, resolved_obj)

    if do_checks and ("$schema" in resolved_obj):
        schema = _get_schema(resolved_obj["$schema"])
        try:
            schema.validate(instance=resolved_obj)
        except ValidationError as e:
            print(f"JSON Schema Validation Error for {rel_path}:")
            print(best_match(schema.iter_errors(resolved_obj)).message)
            exit(1)

    os.chmod(resolved_path, 0o666)


if __name__ == "__main__":
    cmdparser = argparse.ArgumentParser(
        prog="yaml_resolver.py",
        description="Resolves/overlays UDB architecture YAML files",
    )
    subparsers = cmdparser.add_subparsers(dest="command", help="sub-command help")
    merge_parser = subparsers.add_parser(
        "merge", help="Merge overlay on top of architecture files"
    )
    merge_parser.add_argument(
        "arch_dir", type=str, help="Unresolved architecture (input) directory"
    )
    merge_parser.add_argument("overlay_dir", type=str, help="Overlay directory")
    merge_parser.add_argument(
        "merged_dir", type=str, help="Merged architecture (output) directory"
    )
    merge_parser.add_argument(
        "--udb_root", type=str, help="Root of the UDB repo", default=UDB_ROOT
    )

    all_parser = subparsers.add_parser("resolve", help="Resolve all architecture files")
    all_parser.add_argument(
        "arch_dir", type=str, help="Unresolved architecture (input) directory"
    )
    all_parser.add_argument(
        "resolved_dir", type=str, help="Resolved architecture (output) directory"
    )
    all_parser.add_argument(
        "--no-progress", action="store_true", help="Don't display progress bar"
    )
    all_parser.add_argument(
        "--no-checks", action="store_true", help="Don't verify schema"
    )
    all_parser.add_argument(
        "--udb_root", type=str, help="Root of the UDB repo", default=UDB_ROOT
    )

    args = cmdparser.parse_args()

    if args.command == "merge":
        arch_paths = glob.glob(f"**/*.yaml", recursive=True, root_dir=args.arch_dir)
        if args.overlay_dir != None:
            overlay_paths = glob.glob(
                f"**/*.yaml", recursive=True, root_dir=args.overlay_dir
            )
            arch_paths.extend(overlay_paths)
            arch_paths = list(set(arch_paths))
        merged_paths = glob.glob(f"**/*.yaml", recursive=True, root_dir=args.merged_dir)
        arch_paths.extend(merged_paths)
        arch_paths = list(set(arch_paths))

        for arch_path in tqdm(
            arch_paths,
            ascii=True,
            desc="Merging arch",
            file=sys.stderr,
        ):
            merged_arch_path = (
                os.path.join(args.merged_dir, arch_path)
                if os.path.isabs(args.merged_dir)
                else os.path.join(args.udb_root, args.merged_dir, arch_path)
            )
            os.makedirs(os.path.dirname(merged_arch_path), exist_ok=True)
            merge_file(arch_path, args.arch_dir, args.overlay_dir, args.merged_dir)

        print(
            f"[INFO] Merged architecture files written to {args.merged_dir}",
            file=sys.stderr,
        )

    elif args.command == "resolve":
        arch_paths = glob.glob(f"*/**/*.yaml", recursive=True, root_dir=args.arch_dir)
        if os.path.exists(args.resolved_dir):
            resolved_paths = glob.glob(
                f"*/**/*.yaml", recursive=True, root_dir=args.resolved_dir
            )
            arch_paths.extend(resolved_paths)
            arch_paths = list(set(arch_paths))
        iter = (
            arch_paths
            if args.no_progress
            else tqdm(
                arch_paths,
                ascii=True,
                desc="Resolving arch",
                file=sys.stderr,
            )
        )
        abs_resolved_dir = (
            f"{args.udb_root}/{args.resolved_dir}"
            if not os.path.isabs(args.resolved_dir)
            else f"{args.resolved_dir}"
        )
        for arch_path in iter:
            resolved_arch_path = f"{abs_resolved_dir}/{arch_path}"
            os.makedirs(os.path.dirname(resolved_arch_path), exist_ok=True)
            resolve_file(
                arch_path, args.arch_dir, args.resolved_dir, not args.no_checks
            )
        iter = (
            arch_paths
            if args.no_progress
            else tqdm(
                arch_paths,
                ascii=True,
                desc="Validating arch",
                file=sys.stderr,
            )
        )
        for arch_path in iter:
            write_resolved_file_and_validate(
                arch_path, args.resolved_dir, not args.no_checks
            )

        # create index
        write_yaml(f"{abs_resolved_dir}/index.yaml", arch_paths)
        write_json(f"{abs_resolved_dir}/index.json", arch_paths)

        print(
            f"[INFO] Resolved architecture files written to {args.resolved_dir}",
            file=sys.stderr,
        )
