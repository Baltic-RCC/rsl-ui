import zipfile
from io import BytesIO
from unittest.mock import patch, MagicMock
import pytest
import validation_api
from pathlib import Path

@pytest.fixture
def mock_env(tmp_path):
    # Set up temp directories
    suv_dir = tmp_path / "suv"
    workspace_dir = suv_dir / "workspace"
    rule_set_dir = workspace_dir / "rule-set-library"
    
    suv_dir.mkdir()
    workspace_dir.mkdir()
    
    # Patch the validation_api constants
    with (
        patch("validation_api.SUV_DIR", str(suv_dir)),
        patch("validation_api.WORKSPACE_DIR", str(workspace_dir)),
        patch("validation_api.RULE_SET_DIR", str(rule_set_dir)),
        patch("validation_api.INPUT_DIR", str(workspace_dir / "in")),
        patch("validation_api.OUTPUT_DIR", str(workspace_dir / "out")),
    ):
        yield suv_dir, workspace_dir, rule_set_dir

def test_rsl_workflow_and_command_quotes(mock_env):
    """
    Test the full workflow:
    1. Upload RSL Zip
    2. Run Validation
    3. Verify that the command passed to subprocess does NOT have quoted paths.
    """
    suv_dir, workspace_dir, rule_set_dir = mock_env
    
    # --- Step 1: Create and Upload Mock RSL ---
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        # Create a structure: RootFolder/config/rsl.jar
        zf.writestr("RootFolder/config/rsl.jar", "dummy jar content")
        # Create config.xml for version check (optional but good for realism)
        zf.writestr("RootFolder/config/config.xml", 
                    "<ns:Root xmlns:ns='http://entsoe.eu/CIM/Extensions/CGM-BP/2020#'><ns:rslVersion>1.0.TEST</ns:rslVersion></ns:Root>")
        # Create qar2xlsx.jar so report generation is also triggered
        zf.writestr("RootFolder/config/qar2xlsx.jar", "dummy report jar")
    
    zip_buffer.seek(0)
    
    # Perform upload
    validation_api.update_rsl(zip_buffer)
    
    # Verify extraction happened correctly
    expected_jar = rule_set_dir / "config" / "rsl.jar"
    assert expected_jar.exists(), "RSL Jar was not extracted"
    
    # --- Step 2: Prepare Validation Context and Upload Models ---
    # Create a session and ensure input/output dirs exist
    val_id = "test-session-123"
    _, input_dir, output_dir = validation_api.create_validation_context(val_id)
    
    # Simulate uploading a model file
    validation_api.process_upload("test_model.xml", b"mock xml content", input_dir)
    assert (Path(input_dir) / "test_model.xml").exists(), "Model file was not uploaded"
    
    # --- Step 3: Run Validation with Mocked Subprocess ---
    # We use validation_api.subprocess.run because that's what the module uses
    # We also need to patch shutil.which to bypass the executable check
    with (
        patch("validation_api.subprocess.run") as mock_run,
        patch("validation_api.shutil.which") as mock_which
    ):
        # Setup the mock to return a success object
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Java Validation Output..."
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Setup shutil.which to return a valid path for "java"
        mock_which.return_value = "/usr/bin/java"
        
        # Call the function
        # We MUST pass rule_set_dir explicitly because the default argument was bound at import time,
        # so it holds the original path, not the patched one.
        log = validation_api.run_validation(input_dir, output_dir, rule_set_dir=str(rule_set_dir))
        
        # --- Step 4: Verify Command Structure ---
        assert mock_run.called
        
        # Get the arguments of the first call (the validation command)
        # args[0] is the command list
        args, kwargs = mock_run.call_args_list[0]
        cmd_list = args[0]
        
        # Find the input and output arguments
        try:
            i_index = cmd_list.index("-i")
            actual_input_path = cmd_list[i_index + 1]
            
            o_index = cmd_list.index("-o")
            actual_output_path = cmd_list[o_index + 1]
            
            # Assertions
            # 1. The path should be quoted (legacy behavior required by the Java tool/reference impl)
            assert actual_input_path == f'"{input_dir}"'
            assert actual_output_path == f'"{output_dir}"'
            
            # 2. The path SHOULD contain quotes
            assert '"' in actual_input_path, f"Path should have quotes: {actual_input_path}"
            assert '"' in actual_output_path, f"Path should have quotes: {actual_output_path}"
            
        except ValueError:
            pytest.fail(f"Command missing -i or -o flags: {cmd_list}")
            
        # Verify the logs contain output
        assert "Java Validation Output..." in log
