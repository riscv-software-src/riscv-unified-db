#!/usr/bin/env python3
# Copyright (c) Ventana Micro Systems
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""List RISC-V extensions associated with given (or all defined) profile(s).

With no path, the bundled standard database is resolved in memory. Explicit
paths continue to read existing resolved architecture trees. For example:
```
$ ./profile_extensions [--profiles P1[,P2]]
$ ./profile_extensions [--profiles P1[,P2]] $UDB_ROOT/gen/resolved_spec/_
```
"""

import argparse
from collections.abc import Sequence

from udb import Database


def main(argv: Sequence[str] | None = None) -> None:
    """List extensions associated with profiles."""

    parser = argparse.ArgumentParser(description="List extensions associated with profiles")
    parser.add_argument("-p", "--profiles")
    parser.add_argument("paths", nargs="*")
    params = parser.parse_args(argv)

    profiles_filter = []
    if params.profiles is not None:
        profiles_filter = params.profiles.split(",")

    if params.paths:
        profiles = []
        for path in params.paths:
            profiles.extend(Database.from_path(path).profiles)
    else:
        profiles = list(Database.bundled().resolve().profiles)

    for profile in sorted(profiles, key=lambda x: x["name"]):
        if (
            len(profiles_filter) == 0 or profile["name"] in profiles_filter
        ) and "extensions" in profile:
            print(f"{profile['name']}:")
            # convert extensions from dict to array to facilitate sorting by closure
            extensions = []
            for extension, details in profile["extensions"].items():
                if extension.startswith("$"):
                    continue
                extensions.append({**details, "name": extension})

            for extension in sorted(extensions, key=lambda x: f"{x['presence']},{x['name']}"):
                version = "any"
                if "version" in extension:
                    version = extension["version"]
                print(f"- {extension['name']} {version} {extension['presence']}")


if __name__ == "__main__":
    main()
