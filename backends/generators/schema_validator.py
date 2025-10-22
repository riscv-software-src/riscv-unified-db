# backends/generators/schema_validator.py


def validate_entry(entry: dict, required_fields: list, context: str = ""):
    """
    Validate that all required fields exist in a dictionary entry.

    Parameters:
        entry (dict): The dictionary to validate.
        required_fields (list): List of field names, supporting nested fields via dot notation.
        context (str): Optional string describing where this validation is used (for error messages).

    Raises:
        AssertionError: If any required field is missing or the structure is unexpected.
    """
    for field in required_fields:
        keys = field.split(".")
        current = entry
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                ctx = f" in {context}" if context else ""
                raise AssertionError(
                    f"Schema change detected{ctx}: missing field '{field}'"
                )
            current = current[key]
