import os
import shutil
import subprocess
import logging
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
import defusedxml.ElementTree as etree
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Base directory where the Standalone Validation Tool (SVT) is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUV_DIR = os.environ.get("SUV_DIR", os.path.join(BASE_DIR, "suv"))
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", os.path.join(SUV_DIR, "workspace"))
RULE_SET_DIR = os.environ.get(
    "RULE_SET_DIR", os.path.join(WORKSPACE_DIR, "rule-set-library")
)
INPUT_DIR = os.path.join(WORKSPACE_DIR, "in")
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "out")
TEST_DATA_DIR = os.path.join(BASE_DIR, "test_data")  # Directory for test files

# Java configuration
JAVA_HOME = os.environ.get("JAVA_HOME")
if JAVA_HOME:
    JAVA = os.path.join(JAVA_HOME, "bin", "java")
else:
    # Fallback to 'java' in PATH
    JAVA = "java"


def delete_path(path):
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"Deleted: {path}")
    else:
        print(f"Path does not exist: {path}")


def clean_dir(dir: Path):
    for item in dir.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def process_upload(filename, file_bytes, target_dir):
    """
    Process an uploaded file. If it's a zip file, extract its contents (flattened).
    Otherwise, write the file directly.
    Securely handles filenames to prevent path traversal.
    """
    target_path = Path(target_dir)

    if filename.endswith(".zip"):
        try:
            with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
                for member in zf.infolist():
                    # Skip directories
                    if member.is_dir():
                        continue

                    # Flatten structure: use only the basename of the file in the zip
                    # This also handles Zip Slip by ignoring the directory path in the zip
                    safe_name = secure_filename(os.path.basename(member.filename))

                    # Skip files that become empty strings after sanitization (e.g. dotfiles if secure_filename removes them)
                    if not safe_name:
                        continue

                    output_path = target_path / safe_name

                    with zf.open(member) as source, open(output_path, "wb") as target:
                        shutil.copyfileobj(source, target)
            return True
        except zipfile.BadZipFile:
            logger.error(f"Invalid zip file: {filename}")
            # Fallback or raise? For now, if bad zip, maybe treat as file or just fail.
            # We'll treat it as a regular file if zip extraction fails?
            # No, if it ends in .zip but is bad, better to raise or log.
            raise ValueError("Invalid zip file")
    else:
        # Regular file
        safe_name = secure_filename(filename)
        output_path = target_path / safe_name
        with open(output_path, "wb") as f:
            f.write(file_bytes)
    return True


def zip_output_files(output_dir=OUTPUT_DIR):
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


def run_command(command, capture_output=True, timeout=1200):
    """
    Run a command from the /suv directory, optionally capturing output.
    Includes timeout and resilience against hanging processes.
    Timeout defaults to 20 minutes.
    """
    validation_log = []

    # Verify executable exists
    executable = command[0]
    if not shutil.which(executable) and not os.path.exists(executable):
        error_msg = f"Executable not found: {executable}"
        logger.error(error_msg)
        return [error_msg]

    try:
        if capture_output:
            # reading logic switching to subprocess.run for safety
            logger.info(f"Executing command safely: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=SUV_DIR,
                timeout=timeout,
                check=False,  # We handle return code manually
            )

            # Split lines for the log
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
        # Process is killed by subprocess.run automatically on timeout
        raise

    except Exception as e:
        logger.error(f"Command execution error: {str(e)}")
        validation_log.append(f"Error: {str(e)}")
        raise

    return validation_log


def run_validation(
    input_dir=INPUT_DIR,
    output_dir=OUTPUT_DIR,
    validation_gate="full",
    rule_set_dir=RULE_SET_DIR,
):
    validation_log = []

    # Validate validation_gate argument
    valid_gates = ["full", "full_igm", "full_cgm", "bds"]
    if validation_gate not in valid_gates:
        error_msg = f"Invalid validation gate: {validation_gate}. Must be one of {valid_gates}"
        logger.error(error_msg)
        return [error_msg]

    # Resilience: Check if JARs exist
    rsl_jar = os.path.join(rule_set_dir, "config", "rsl.jar")
    if not os.path.exists(rsl_jar):
        msg = f"CRITICAL: Validation JAR not found at {rsl_jar}. Please upload RSL."
        logger.error(msg)
        return [msg]

    validation_cmd = [
        JAVA,
        "-jar",
        rsl_jar,
        "-i",
        f'"{input_dir}"',
        "-o",
        f'"{output_dir}"',
        "-vg",
        validation_gate,
        "-c",
        os.path.join(rule_set_dir, "config"),
    ]

    # Construct the report generation command
    qar_jar = os.path.join(rule_set_dir, "config", "qar2xlsx.jar")
    # Check if report JAR exists
    report_cmd = None
    if os.path.exists(qar_jar):
        report_cmd = [JAVA, "-jar", qar_jar, f"{output_dir}"]
    else:
        logger.warning(f"Report generation JAR not found at {qar_jar}")

    try:
        logger.info(f"Running validation with command: {' '.join(validation_cmd)}")
        validation_log.extend(run_command(validation_cmd, capture_output=True))
    except subprocess.CalledProcessError as e:
        error_text = f"Validation failed with return code {e.returncode}"
        logger.error(error_text)
        if e.stderr:
            logger.error(f"Stderr: {e.stderr}")
        validation_log.append(error_text)
        # Even if validation fails, we might want to try reporting or just return logs
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

    return validation_log


def download_validation_results(output_dir=OUTPUT_DIR):
    return zip_output_files(output_dir)


def create_validation_context(validation_instance=None):
    if not validation_instance:
        validation_instance = str(uuid.uuid4())

    validation_base_path = os.path.join(WORKSPACE_DIR, f"temp_{validation_instance}")
    validation_input_path = os.path.join(validation_base_path, "in")
    validation_output_path = os.path.join(validation_base_path, "out")

    required_dirs = [validation_input_path, validation_output_path]
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            logger.warning(
                f"Required SUV directory not found: {dir_path}, creating it for test"
            )
            os.makedirs(dir_path, exist_ok=True)

    return validation_base_path, validation_input_path, validation_output_path


def get_ruleset_version():
    try:
        tree = etree.parse(os.path.join(RULE_SET_DIR, "config", "config.xml"))
        root = tree.getroot()
        rsl_version = root.find(
            "{http://entsoe.eu/CIM/Extensions/CGM-BP/2020#}rslVersion"
        ).text
        return rsl_version
    except Exception:
        return None


def is_configured():
    """Check if the RSL JAR exists and the system is ready for validation."""
    rsl_jar = os.path.join(RULE_SET_DIR, "config", "rsl.jar")
    return os.path.exists(rsl_jar)


def update_rsl(rsl_zip_bytes: BytesIO):
    """
    Update the rule-set-library with the contents of the first internal folder of the provided RSL zip file.

    Args:
        rsl_zip_bytes (BytesIO): In-memory bytes of the RSL zip file.
    """
    try:
        # Ensure the rule-set-library directory exists
        rule_set_dir = Path(RULE_SET_DIR)
        if not rule_set_dir.exists():
            rule_set_dir.mkdir(parents=True, exist_ok=True)

        # Clean the existing rule-set-library directory
        clean_dir(rule_set_dir)

        # Open the zip file from the BytesIO object
        with zipfile.ZipFile(rsl_zip_bytes, "r") as zip_ref:
            # Get the list of files/folders in the zip
            zip_contents = zip_ref.namelist()

            # Find the first internal folder (assuming it's the common prefix)
            if not zip_contents:
                raise ValueError("Zip file is empty")

            # Determine the root folder (first common prefix)
            # Use top-level directory check
            top_level_items = {item.split("/")[0] for item in zip_contents}
            if len(top_level_items) != 1:
                raise ValueError("Zip file does not contain a single root folder")

            root_folder = list(top_level_items)[0] + "/"

            # Strip the root folder and extract contents
            for file_info in zip_ref.infolist():
                # Skip directories and files outside the root folder
                if (
                    file_info.filename.startswith(root_folder)
                    and not file_info.is_dir()
                ):
                    # Remove the root folder prefix from the file path
                    relative_path = file_info.filename[len(root_folder) :]
                    if relative_path:  # Ensure there's a remaining path after stripping
                        target_path = rule_set_dir / relative_path
                        # Ensure the target directory exists
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        # Extract the file to the target path
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
            validation_base_path, validation_input_path, validation_output_path = (
                create_validation_context()
            )

            logger.info(
                f"Copying files from {TEST_DATA_DIR} to {validation_input_path}"
            )
            for filename in os.listdir(TEST_DATA_DIR):
                src_path = os.path.join(TEST_DATA_DIR, filename)
                dst_path = os.path.join(validation_input_path, filename)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)

            result = run_validation(
                input_dir=validation_input_path, output_dir=validation_output_path
            )
            if result:
                logger.info(f"Validation successful, report generated at: {result}")
            else:
                logger.error("Validation failed or no report generated")

        except Exception as e:
            logger.error(f"Test failed: {e}")

        finally:
            logger.info(
                f"Test completed, input and output remain at {validation_input_path} and {validation_output_path}"
            )
