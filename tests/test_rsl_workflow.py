import zipfile
import uuid
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import validation_api


@pytest.fixture
def mock_fs(tmp_path):
    """
    Sets up a temporary directory structure for testing.
    """
    suv_dir = tmp_path / "suv"
    workspace_dir = suv_dir / "workspace"
    rule_set_dir = workspace_dir / "rule-set-library"

    suv_dir.mkdir()
    workspace_dir.mkdir()
    rule_set_dir.mkdir()

    # Patch the validation_api constants
    with (
        patch("validation_api.SUV_DIR", str(suv_dir)),
        patch("validation_api.WORKSPACE_DIR", str(workspace_dir)),
        patch("validation_api.RULE_SET_DIR", str(rule_set_dir)),
        patch("validation_api.INPUT_DIR", str(workspace_dir / "in")),
        patch("validation_api.OUTPUT_DIR", str(workspace_dir / "out")),
    ):
        yield suv_dir, workspace_dir, rule_set_dir


def test_full_workflow(mock_fs):
    """
    Simulates the full workflow:
    1. Upload RSL
    2. Upload Model
    3. Run Validation
    """
    suv_dir, workspace_dir, rule_set_dir = mock_fs

    # --- Step 1: Create and Upload Mock RSL ---
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        # Create a structure: RootFolder/config/rsl.jar
        zf.writestr("MyRSL/config/rsl.jar", "dummy jar content")
        zf.writestr(
            "MyRSL/config/config.xml",
            "<rsl><entsoe:rslVersion xmlns:entsoe='http://entsoe.eu/CIM/Extensions/CGM-BP/2020#'>1.0</entsoe:rslVersion></rsl>",
        )

    zip_buffer.seek(0)

    # Call the update logic
    validation_api.update_rsl(zip_buffer)

    # Check if RSL was extracted correctly (stripped root folder)
    assert (rule_set_dir / "config" / "rsl.jar").exists(), "RSL Jar not found"
    assert (rule_set_dir / "config" / "config.xml").exists(), "Config XML not found"

    # --- Step 2: Upload a Model File ---
    # Create a session and ensure input/output dirs exist
    # Create context
    val_id = str(uuid.uuid4())
    _, input_dir, output_dir = validation_api.prepare_session(val_id)

    # 1. Upload RSL
    validation_api.process_upload("test_model.xml", b"mock xml content", input_dir)
    assert (Path(input_dir) / "test_model.xml").exists(), "Model file was not uploaded"

    # --- Step 3: Run Validation with Mocked Subprocess ---
    # We also need to patch shutil.which to bypass the executable check
    with (
        patch("validation_api.subprocess.run") as mock_run,
        patch("validation_api.shutil.which") as mock_which,
        patch("validation_api.JAVA", "/usr/bin/java"),
    ):
        # Setup the mock to return a success object
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Java Validation Output..."
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Mock shutil.which to return True (found)
        mock_which.return_value = "/usr/bin/java"

        # Run validation
        log = validation_api.run_validation(input_dir, output_dir)

        # Assertions
        assert "Java Validation Output..." in log
        mock_run.assert_called()

        # Verify arguments
        args, _ = mock_run.call_args
        command_list = args[0]
        assert (
            command_list[0] == "/usr/bin/java"
        )  # From Config.JAVA_HOME fallback or mocked logic?
        # validation_api uses JAVA variable.
        # If JAVA_HOME is set in env, it uses it.
        # We didn't patch Config.JAVA_HOME, but logic uses validation_api.JAVA.
        # We can check if "-jar" is in the command
        assert "-jar" in command_list
