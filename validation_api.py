import os
import shutil
import subprocess
import logging
import uuid
import zipfile
import json
import threading
import base64
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Optional, Any

import defusedxml.ElementTree as etree
from werkzeug.utils import secure_filename

from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Configuration & Paths ---
BASE_DIR = Config.BASE_DIR
SUV_DIR = Config.SUV_DIR
WORKSPACE_DIR = Config.WORKSPACE_DIR
RULE_SET_DIR = Config.RULE_SET_DIR
INPUT_DIR = os.path.join(WORKSPACE_DIR, "in")
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "out")
TEST_DATA_DIR = Config.TEST_DATA_DIR

# Java configuration
JAVA_HOME = Config.JAVA_HOME
if JAVA_HOME:
    JAVA = os.path.join(JAVA_HOME, "bin", "java")
else:
    JAVA = "java"


# --- Helper Functions ---


def delete_path(path: str) -> None:
    """Deletes a file or directory if it exists."""
    if os.path.exists(path):
        shutil.rmtree(path)
        logger.info(f"Deleted: {path}")
    else:
        logger.warning(f"Path does not exist: {path}")


def clean_dir(directory: Path, keep_pattern: Optional[str] = None) -> None:
    """
    Removes all files and subdirectories inside a directory.
    If keep_pattern is provided, files/folders with that substring in their name are preserved.
    """
    if not directory.exists():
        return
    for item in directory.iterdir():
        if keep_pattern and keep_pattern in item.name:
            continue

        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def get_status_file_path(session_id: str) -> str:
    """Returns the absolute path to the status file for a given session."""
    return os.path.join(WORKSPACE_DIR, f"temp_{session_id}", "status.json")


def prepare_session(session_id: str) -> Tuple[str, str, str]:
    """
    Creates the workspace directories for a session if they don't exist.
    Returns: (base_dir, input_dir, output_dir)
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    validation_base_path = os.path.join(WORKSPACE_DIR, f"temp_{session_id}")
    validation_input_path = os.path.join(validation_base_path, "in")
    validation_output_path = os.path.join(validation_base_path, "out")

    required_dirs = [validation_input_path, validation_output_path]
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

    return validation_base_path, validation_input_path, validation_output_path


def process_upload(filename: str, file_bytes: bytes, target_dir: str) -> bool:
    """
    Process an uploaded file. If it's a zip file, extract its contents (flattened).
    Otherwise, write the file directly.
    Securely handles filenames to prevent path traversal and ZIP bombs.
    """
    target_path = Path(target_dir)

    if filename.endswith(".zip"):
        try:
            with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue

                    # Security: Protect against Zip Bombs (uncompressed size check)
                    if member.file_size > Config.MAX_CONTENT_LENGTH:
                        error_msg = f"Security Alert: File {member.filename} in ZIP exceeds allowed size limit."
                        logger.error(error_msg)
                        raise ValueError(error_msg)

                    safe_name = secure_filename(os.path.basename(member.filename))
                    if not safe_name:
                        continue

                    output_path = target_path / safe_name
                    with zf.open(member) as source, open(output_path, "wb") as target:
                        shutil.copyfileobj(source, target)
            return True
        except zipfile.BadZipFile:
            logger.error(f"Invalid zip file: {filename}")
            raise ValueError("Invalid zip file")
        except Exception as e:
            logger.error(f"Error processing zip upload: {e}")
            raise
    else:
        safe_name = secure_filename(filename)
        output_path = target_path / safe_name
        try:
            with open(output_path, "wb") as f:
                f.write(file_bytes)
        except OSError as e:
            logger.error(f"Error writing file {safe_name}: {e}")
            raise
    return True


def save_base64_upload(filename: str, base64_content: str, target_dir: str) -> bool:
    """Decodes a base64 string and processes it as an uploaded file."""
    try:
        # Handle cases where base64 string might have a header (e.g. data:text/xml;base64,...)
        if "," in base64_content:
            base64_content = base64_content.split(",")[1]

        decoded = base64.b64decode(base64_content)
        return process_upload(filename, decoded, target_dir)
    except Exception as e:
        logger.error(f"Failed to save base64 upload {filename}: {e}")
        raise


def zip_output_files(output_dir: str = OUTPUT_DIR) -> BytesIO:
    """Zip all files in the output directory and return as a BytesIO object."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zip_file.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer


def download_validation_results(output_dir: str = OUTPUT_DIR) -> BytesIO:
    """Alias for zip_output_files for API compatibility."""
    return zip_output_files(output_dir)


def reset_workspace(
    input_dir: str, output_dir: str, keep_pattern: Optional[str] = None
) -> None:
    """
    Cleans the workspace directories.

    Args:
        input_dir: Path to the input directory.
        output_dir: Path to the output directory.
        keep_pattern: If provided, files in the input directory matching this pattern are preserved.
                      If None, all files in the input directory are deleted.
                      The output directory is always fully cleaned.
    """
    clean_dir(Path(output_dir))
    clean_dir(Path(input_dir), keep_pattern=keep_pattern)


def run_command(
    command: List[str],
    capture_output: bool = True,
    timeout: int = Config.VALIDATION_TIMEOUT,
) -> List[str]:
    """
    Run a command from the /suv directory.
    """
    validation_log = []
    executable = command[0]

    if not shutil.which(executable) and not os.path.exists(executable):
        error_msg = f"Executable not found: {executable}"
        logger.error(error_msg)
        return [error_msg]

    try:
        if capture_output:
            logger.info(f"Executing command safely: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=SUV_DIR,
                timeout=timeout,
                check=False,
            )
            validation_log.extend(result.stdout.splitlines())
            if result.stderr:
                validation_log.extend(result.stderr.splitlines())

            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode,
                    command,
                    output=result.stdout,
                    stderr=result.stderr,
                )
        else:
            subprocess.run(command, cwd=SUV_DIR, timeout=timeout, check=True)

    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout} seconds: {' '.join(command)}"
        logger.error(error_msg)
        validation_log.append(error_msg)
        raise
    except Exception as e:
        logger.error(f"Command execution error: {str(e)}")
        validation_log.append(f"Error: {str(e)}")
        raise

    return validation_log


def update_status(
    status_file: Optional[str],
    state: str,
    progress: int,
    message: str,
    result: Optional[Any] = None,
) -> None:
    """Updates the status JSON file with the current progress/state."""
    if not status_file:
        return
    try:
        data = {
            "state": state,
            "progress": progress,
            "message": message,
            "result": result,
        }
        with open(status_file, "w") as f:
            json.dump(data, f)
    except OSError as e:
        logger.error(f"Failed to update status file {status_file}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error updating status: {e}")


def run_validation_background(
    input_dir: str,
    output_dir: str,
    validation_gate: str,
    rule_set_dir: str,
    status_file: str,
) -> None:
    """Executes run_validation in a background thread and updates the status file."""

    def task():
        try:
            result = run_validation(
                input_dir,
                output_dir,
                validation_gate=validation_gate,
                rule_set_dir=rule_set_dir,
                status_file=status_file,
            )
            update_status(status_file, "completed", 100, "Validation complete", result)
        except Exception as e:
            logger.error(f"Background validation failed: {e}")
            update_status(
                status_file, "error", 100, f"Validation error: {str(e)}", [str(e)]
            )

    thread = threading.Thread(target=task)
    thread.daemon = True
    thread.start()


def _build_validation_command(
    input_dir: str, output_dir: str, validation_gate: str, rule_set_dir: str
) -> List[str]:
    """Constructs the command list for the validation tool."""
    rsl_jar = os.path.join(rule_set_dir, "config", "rsl.jar")
    return [
        JAVA,
        "-jar",
        rsl_jar,
        "-i",
        input_dir,
        "-o",
        output_dir,
        "-vg",
        validation_gate,
        "-c",
        os.path.join(rule_set_dir, "config"),
    ]


def _build_report_command(output_dir: str, rule_set_dir: str) -> Optional[List[str]]:
    """Constructs the command list for the report generation tool if it exists."""
    qar_jar = os.path.join(rule_set_dir, "config", "qar2xlsx.jar")
    if os.path.exists(qar_jar):
        return [JAVA, "-jar", qar_jar, output_dir]
    return None


def run_validation(
    input_dir: str = INPUT_DIR,
    output_dir: str = OUTPUT_DIR,
    validation_gate: str = "full",
    rule_set_dir: Optional[str] = None,
    status_file: Optional[str] = None,
) -> List[str]:
    """
    Runs the Java validation tool and generates an Excel report.
    Returns: A list of log strings.
    """
    validation_log: List[str] = []

    if rule_set_dir is None:
        rule_set_dir = RULE_SET_DIR

    valid_gates = ["full", "full_igm", "full_cgm", "bds"]
    if validation_gate not in valid_gates:
        error_msg = (
            f"Invalid validation gate: {validation_gate}. Must be one of {valid_gates}"
        )
        logger.error(error_msg)
        update_status(status_file, "error", 0, error_msg)
        return [error_msg]

    update_status(status_file, "running", 5, "Initializing validation...")

    # Resilience: Check if JARs exist
    rsl_jar = os.path.join(rule_set_dir, "config", "rsl.jar")
    if not os.path.exists(rsl_jar):
        msg = f"CRITICAL: Validation JAR not found at {rsl_jar}. Please upload RSL."
        logger.error(msg)
        update_status(status_file, "error", 0, msg)
        return [msg]

    validation_cmd = _build_validation_command(
        input_dir, output_dir, validation_gate, rule_set_dir
    )
    report_cmd = _build_report_command(output_dir, rule_set_dir)

    try:
        logger.info(f"Running validation with command: {' '.join(validation_cmd)}")
        update_status(status_file, "running", 10, "Running Validation Tool...")
        validation_log.extend(run_command(validation_cmd, capture_output=True))
    except subprocess.CalledProcessError as e:
        error_text = f"Validation failed with return code {e.returncode}"
        logger.error(error_text)
        if e.stderr:
            logger.error(f"Stderr: {e.stderr}")
        validation_log.append(error_text)
        return validation_log
    except subprocess.TimeoutExpired:
        validation_log.append("Validation timed out.")
        return validation_log
    except Exception as e:
        validation_log.append(f"Unexpected error during validation: {str(e)}")
        return validation_log

    if report_cmd:
        try:
            logger.info(f"Generating report with command: {' '.join(report_cmd)}")
            update_status(status_file, "running", 50, "Generating Report...")
            validation_log.extend(run_command(report_cmd, capture_output=True))
        except subprocess.CalledProcessError as e:
            error_text = [
                f"Excel Report generation failed: {e.returncode}",
                "Make sure that config/qar2xslx.jar is in RSL ZIP",
            ]
            logger.error(error_text)
            validation_log.extend(error_text)
        except Exception as e:
            validation_log.append(f"Error generating report: {str(e)}")

    update_status(status_file, "running", 90, "Finalizing...")
    return validation_log


def get_ruleset_version() -> Optional[str]:
    """Parses the RSL config.xml to get the version string."""
    try:
        tree = etree.parse(os.path.join(RULE_SET_DIR, "config", "config.xml"))
        root = tree.getroot()
        rsl_version = root.find(
            "{http://entsoe.eu/CIM/Extensions/CGM-BP/2020#}rslVersion"
        ).text
        return rsl_version
    except Exception:
        return None


def is_configured() -> bool:
    """Check if the RSL JAR exists and the system is ready for validation."""
    rsl_jar = os.path.join(RULE_SET_DIR, "config", "rsl.jar")
    return os.path.exists(rsl_jar)


def update_rsl_from_base64(base64_content: str) -> None:
    """Decodes a base64 string and updates the RSL."""
    if "," in base64_content:
        base64_content = base64_content.split(",")[1]
    decoded = base64.b64decode(base64_content)
    update_rsl(BytesIO(decoded))


def update_rsl(rsl_zip_bytes: BytesIO) -> None:
    """
    Update the rule-set-library with the contents of the first internal folder of the provided RSL zip file.
    Securely handles ZIP extraction and checks for uncompressed size limits.
    """
    try:
        rule_set_dir = Path(RULE_SET_DIR)
        if not rule_set_dir.exists():
            rule_set_dir.mkdir(parents=True, exist_ok=True)

        clean_dir(rule_set_dir)

        with zipfile.ZipFile(rsl_zip_bytes, "r") as zip_ref:
            zip_contents = zip_ref.namelist()
            if not zip_contents:
                raise ValueError("Zip file is empty")

            top_level_items = {item.split("/")[0] for item in zip_contents}
            if len(top_level_items) != 1:
                raise ValueError("Zip file does not contain a single root folder")

            root_folder = list(top_level_items)[0] + "/"

            for file_info in zip_ref.infolist():
                if (
                    file_info.filename.startswith(root_folder)
                    and not file_info.is_dir()
                ):
                    # Security: Protect against Zip Bombs
                    if file_info.file_size > Config.MAX_CONTENT_LENGTH:
                        error_msg = f"Security Alert: File {file_info.filename} in RSL ZIP exceeds allowed size limit."
                        logger.error(error_msg)
                        raise ValueError(error_msg)

                    relative_path = file_info.filename[len(root_folder) :]
                    if relative_path:
                        target_path = rule_set_dir / relative_path
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with (
                            zip_ref.open(file_info) as source,
                            open(target_path, "wb") as target,
                        ):
                            shutil.copyfileobj(source, target)

        logger.info(
            "RSL updated successfully from in-memory zip data, stripped root folder"
        )
    except Exception as e:
        logger.error(f"Failed to update RSL: {str(e)}")
        raise


if __name__ == "__main__":
    if not os.path.exists(TEST_DATA_DIR) or not os.listdir(TEST_DATA_DIR):
        logger.warning(f"No files found in {TEST_DATA_DIR}, skipping test")
    else:
        try:
            base_p, input_p, output_p = prepare_session("test_session")

            logger.info(f"Copying files from {TEST_DATA_DIR} to {input_p}")
            for filename in os.listdir(TEST_DATA_DIR):
                src_path = os.path.join(TEST_DATA_DIR, filename)
                dst_path = os.path.join(input_p, filename)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)

            result = run_validation(input_dir=input_p, output_dir=output_p)
            if result:
                logger.info(f"Validation successful: {result}")
            else:
                logger.error("Validation failed")
        except Exception as e:
            logger.error(f"Test failed: {e}")
