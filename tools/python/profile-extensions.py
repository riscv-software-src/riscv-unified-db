#!/usr/bin/env python3
# Copyright (c) Ventana Micro Systems
# SPDX-License-Identifier: BSD-3-Clause-Clear

import argparse
import UDB


def main():
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
        profiles += UDB.find_and_load_yaml(path, ["profile"])

    for profile in sorted(profiles, key=lambda x: x["name"]):
        if (
            len(profiles_filter) == 0 or profile["name"] in profiles_filter
        ) and "extensions" in profile:
            print(f"{profile['name']}:")
            if "$child_of" in profile["extensions"]:
                del profile["extensions"]["$child_of"]
            if "$parent_of" in profile["extensions"]:
                del profile["extensions"]["$parent_of"]
            for extension in sorted(
                profile["extensions"],
                key=lambda x: f"{profile['extensions'][x]['presence']},{x}",
            ):
                version = "any"
                if "version" in profile["extensions"][extension]:
                    version = profile["extensions"][extension]["version"]
                print(
                    f"-  {extension} {version} {profile['extensions'][extension]['presence']}"
                )


if __name__ == "__main__":
    main()
