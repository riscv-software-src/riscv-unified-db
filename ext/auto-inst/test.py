import pytest
import os
from parsing import run_parser

@pytest.fixture
def setup_paths(request):
    json_file = request.config.getoption("--json_file")
    repo_dir = request.config.getoption("--repo_dir")

    # Resolve absolute paths
    json_file = os.path.abspath(json_file)
    repo_dir = os.path.abspath(repo_dir)
    output_file = os.path.join(repo_dir, "output.txt")

    print(f"Using JSON File: {json_file}")
    print(f"Using Repository Directory: {repo_dir}")
    print(f"Output File Path: {output_file}")

    return json_file, repo_dir, output_file

def test_run_parser_mimic_old_behavior(setup_paths):
    json_file, repo_dir, output_file = setup_paths

    # Run the parser (similar to old behavior)
    result = run_parser(json_file, repo_dir, output_file=output_file)

    if result is None:
        print("WARNING: No instructions found or an error occurred. (Mimic old script warning)")
        # You could fail here if this was previously considered a hard error
        pytest.fail("No output produced by run_parser.")

    # Check output file content
    if not os.path.exists(output_file):
        print("ERROR: output.txt was not created. (Mimic old script error)")
        pytest.fail("Output file was not created.")

    with open(output_file, 'r') as f:
        content = f.read()

    # Mimic old behavior: print warnings if no instructions found
    if "Total Instructions Found: 0" in content:
        print("WARNING: No instructions found in output.txt (Mimic old script warning)")

    # Check for encoding differences
    # In the original script, encoding mismatches were printed like:
    # "Encodings do not match. Differences:"
    # If we find that line, we mimic the old error messages
    if "Encodings do not match. Differences:" in content:
        # Extract differences lines
        lines = content.splitlines()
        diff_lines = [line for line in lines if line.strip().startswith("-")]
        print("ERROR: Encoding differences found! (Mimic old script error)")
        pytest.fail("Encodings do not match as per old behavior.")

    # If we reach here, we mimic the old success output
    print("No warnings or errors detected. Test passes but mimics old success behavior.")
