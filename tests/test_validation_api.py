import os
import pytest
from unittest.mock import patch
from io import BytesIO
import zipfile
import validation_api
from pathlib import Path


@pytest.fixture
def mock_fs(tmp_path):
    """Fixture to mock file system paths."""
    # Patch the constants in validation_api to use the temporary directory
    with (
        patch("validation_api.WORKSPACE_DIR", str(tmp_path / "workspace")),
        patch("validation_api.SUV_DIR", str(tmp_path)),
        patch(
            "validation_api.RULE_SET_DIR",
            str(tmp_path / "workspace" / "rule-set-library"),
        ),
    ):
        yield tmp_path


def test_create_validation_context(mock_fs):
    """Test creation of validation context (directories)."""
    base, inp, out = validation_api.create_validation_context("test-uuid")

    assert "test-uuid" in base
    assert os.path.exists(inp)
    assert os.path.exists(out)


@patch("validation_api.run_command")
def test_run_validation_success(mock_run_command, mock_fs):
    """Test run_validation calls the correct commands."""
    # Create dummy directories
    base, inp, out = validation_api.create_validation_context("test-uuid")

    # Create dummy JARs to pass existence check
    config_dir = Path(validation_api.RULE_SET_DIR) / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "rsl.jar").touch()
    (config_dir / "qar2xlsx.jar").touch()

    # Mock successful execution
    mock_run_command.return_value = ["Log line 1", "Log line 2"]

    rule_set_dir = str(Path(validation_api.RULE_SET_DIR))
    log = validation_api.run_validation(
        input_dir=inp, output_dir=out, rule_set_dir=rule_set_dir
    )

    assert log is not None
    assert len(mock_run_command.call_args_list) == 2  # Validation + Report
    assert "Log line 1" in log


@patch("validation_api.run_command")
def test_run_validation_failure(mock_run_command, mock_fs):
    """Test run_validation handles failure."""
    base, inp, out = validation_api.create_validation_context("test-uuid")

    # Create dummy JARs to pass existence check
    config_dir = Path(validation_api.RULE_SET_DIR) / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "rsl.jar").touch()

    # Mock failure
    mock_run_command.side_effect = validation_api.subprocess.CalledProcessError(
        1, "cmd"
    )

    rule_set_dir = str(Path(validation_api.RULE_SET_DIR))
    log = validation_api.run_validation(
        input_dir=inp, output_dir=out, rule_set_dir=rule_set_dir
    )

    # Updated: now returns log with error message instead of None
    assert log is not None
    assert any("Validation failed" in line for line in log)


@patch("validation_api.run_command")
def test_run_validation_valid_gates(mock_run_command, mock_fs):
    """Test run_validation accepts valid validation gates."""
    base, inp, out = validation_api.create_validation_context("test-uuid")
    
    # Create dummy JARs
    config_dir = Path(validation_api.RULE_SET_DIR) / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "rsl.jar").touch()
    
    mock_run_command.return_value = ["Success"]

    for gate in ["full", "full_igm", "full_cgm", "bds"]:
        validation_api.run_validation(
            input_dir=inp, output_dir=out, rule_set_dir=str(validation_api.RULE_SET_DIR),
            validation_gate=gate
        )
        
        args, _ = mock_run_command.call_args
        cmd = args[0]
        assert "-vg" in cmd
        idx = cmd.index("-vg")
        assert cmd[idx + 1] == gate


@patch("validation_api.run_command")
def test_run_validation_invalid_gate(mock_run_command, mock_fs):
    """Test run_validation rejects invalid validation gate."""
    base, inp, out = validation_api.create_validation_context("test-uuid")
    
    # Create dummy JARs
    config_dir = Path(validation_api.RULE_SET_DIR) / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "rsl.jar").touch()

    log = validation_api.run_validation(
        input_dir=inp, output_dir=out, rule_set_dir=str(validation_api.RULE_SET_DIR),
        validation_gate="invalid_gate"
    )

    assert any("Invalid validation gate" in line for line in log)
    assert not mock_run_command.called


def test_update_rsl(mock_fs):
    """Test RSL update from zip."""
    # Create a dummy zip file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("root_folder/config/config.xml", "<rslVersion>1.0</rslVersion>")
    zip_buffer.seek(0)

    validation_api.update_rsl(zip_buffer)

    expected_file = os.path.join(validation_api.RULE_SET_DIR, "config", "config.xml")
    assert os.path.exists(expected_file)
    with open(expected_file, "r") as f:
        content = f.read()
    assert "<rslVersion>1.0</rslVersion>" in content
