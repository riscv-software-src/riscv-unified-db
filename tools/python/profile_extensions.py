#!/usr/bin/env python3
# Copyright (c) Ventana Micro Systems
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""List RISC-V extensions associated with given (or all defined) profile(s).

It is generally expected to be used with a "resolved architectural specification".
So, for example:
```
$ ./profile_extensions [--profiles P1[,P2]] $UDB_ROOT/gen/resolved_spec/_
```
"""

import argparse

import udb


def main() -> None:
    """List extensions associated with profiles."""

    parser = argparse.ArgumentParser(
        description="List extensions associated with profiles"
    )
    parser.add_argument("-p", "--profiles")
    parser.add_argument("paths", nargs="*", default=".")
    params = parser.parse_args()

    profiles_filter = []
    if params.profiles is not None:
        for profile in params.profiles.split(","):
            profiles_filter.append(profile)

    profiles = []
    for path in params.paths:
        profiles += udb.find_and_load_yaml(path, ["profile"])

    for profile in sorted(profiles, key=lambda x: x["name"]):
        if (
            len(profiles_filter) == 0 or profile["name"] in profiles_filter
        ) and "extensions" in profile:
            print(f"{profile['name']}:")
            if "$child_of" in profile["extensions"]:
                del profile["extensions"]["$child_of"]
            if "$parent_of" in profile["extensions"]:
                del profile["extensions"]["$parent_of"]

            # convert extensions from dict to array to facilitate sorting by closure
            extensions = []
            for extension in profile["extensions"]:
                profile["extensions"][extension]["name"] = extension
                extensions.append(profile["extensions"][extension])

            for extension in sorted(
                extensions, key=lambda x: f"{x['presence']},{x['name']}"
            ):
                version = "any"
                if "version" in extension:
                    version = extension["version"]
                print(f"- {extension['name']} {version} {extension['presence']}")


if __name__ == "__main__":
    main()
