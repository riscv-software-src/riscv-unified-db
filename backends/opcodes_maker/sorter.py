import json


def sort_instr_json(dir_name, outname):
    with open(dir_name) as file:
        data = json.load(file)

    sorted_data = {}
    for key in sorted(data):
        entry = data[key]
        if "variable_fields" in entry:
            entry["variable_fields"] = sorted(entry["variable_fields"])
        if "extension" in entry:
            entry["extension"] = sorted(entry["extension"])

        # Add the processed entry to the sorted data
        sorted_data[key] = entry

    # Write the sorted data with an indentation of 2 spaces
    with open(outname, "w") as file:
        json.dump(sorted_data, file, indent=2)

    print(json.dumps(sorted_data, indent=2))


def main():
    # Uncomment and adjust file names as needed
    # sort_instr_json("instr_dict.json", "udb_sorted_data.json")
    sort_instr_json("processed_instr_dict.json", "sorted_instr_dict.json")


main()
