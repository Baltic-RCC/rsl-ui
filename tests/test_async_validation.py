import os
import json
import time
from unittest.mock import patch
import validation_api
from config import Config


def test_update_status(tmp_path):
    status_file = tmp_path / "status.json"

    # Test creation
    validation_api.update_status(str(status_file), "running", 10, "Starting")
    assert status_file.exists()

    with open(status_file) as f:
        data = json.load(f)
        assert data["state"] == "running"
        assert data["progress"] == 10
        assert data["message"] == "Starting"

    # Test update
    validation_api.update_status(str(status_file), "completed", 100, "Done", ["Log"])
    with open(status_file) as f:
        data = json.load(f)
        assert data["state"] == "completed"
        assert data["result"] == ["Log"]


@patch("validation_api.run_validation")
def test_run_validation_background(mock_run_validation, tmp_path):
    # Setup
    input_dir = str(tmp_path / "in")
    output_dir = str(tmp_path / "out")
    status_file = str(tmp_path / "status.json")
    os.makedirs(input_dir)
    os.makedirs(output_dir)

    mock_run_validation.return_value = ["Success"]

    # Run
    validation_api.run_validation_background(
        input_dir, output_dir, "full", str(Config.RULE_SET_DIR), status_file
    )

    # Wait for thread to finish (it's fast since mocked)
    timeout = 5
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(status_file):
            with open(status_file) as f:
                try:
                    data = json.load(f)
                    if data.get("state") == "completed":
                        break
                except (json.JSONDecodeError, OSError):
                    pass
        time.sleep(0.1)

    # Assert
    assert os.path.exists(status_file)
    with open(status_file) as f:
        data = json.load(f)
        assert data["state"] == "completed"
        assert data["result"] == ["Success"]

    mock_run_validation.assert_called_once()
