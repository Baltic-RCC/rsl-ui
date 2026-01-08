import os
import pytest
import validation_api
from unittest.mock import patch


@pytest.fixture
def mock_workspace(tmp_path):
    with patch("validation_api.WORKSPACE_DIR", str(tmp_path)):
        yield tmp_path


def test_path_traversal_validation_context(mock_workspace):
    """
    Security Test: Ensure that directory traversal characters in the validation ID
    do not allow creation of directories outside the WORKSPACE_DIR.
    """
    # Attempt to break out of the workspace directory
    # If WORKSPACE_DIR is /tmp/workspace
    # malicious_id = "../../etc"
    # Resulting path should NOT be /etc

    malicious_id = "../outside_workspace"

    base, inp, out = validation_api.create_validation_context(malicious_id)

    # The base path should start with the mock_workspace path
    # os.path.abspath resolves '..' so we need to check if the common prefix is still the workspace
    resolved_base = os.path.abspath(base)
    resolved_workspace = os.path.abspath(str(mock_workspace))

    assert resolved_base.startswith(resolved_workspace), (
        f"Path Traversal Detected! Path {resolved_base} escaped {resolved_workspace}"
    )


def test_file_upload_traversal(mock_workspace):
    """
    Security Test: Check if secure_filename prevents writing outside input dir.
    """
    from werkzeug.utils import secure_filename

    input_dir = mock_workspace / "safe_input"
    os.makedirs(input_dir, exist_ok=True)

    malicious_filename = "../../evil.txt"
    sanitized_filename = secure_filename(malicious_filename)

    # Logic simulating the fixed web-app.py
    from pathlib import Path

    file_path = Path(input_dir) / sanitized_filename

    # Resolve the path
    resolved_path = file_path.resolve()
    resolved_input = input_dir.resolve()

    try:
        is_relative = resolved_path.is_relative_to(resolved_input)
    except AttributeError:
        # Python < 3.9
        is_relative = str(resolved_path).startswith(str(resolved_input))

    assert is_relative, (
        f"Path Traversal persisted! {resolved_path} is not inside {resolved_input}"
    )
    assert ".." not in sanitized_filename
