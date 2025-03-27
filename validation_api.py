import os
import shutil
import subprocess
import logging
import uuid
import zipfile
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directory where the Standalone Validation Tool (SVT) is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUV_DIR = os.path.join(BASE_DIR, "suv")
WORKSPACE_DIR = os.path.join(SUV_DIR, "workspace")  # Hardcoded as /suv/workspace
RULE_SET_DIR = os.path.join(WORKSPACE_DIR, "rule-set-library")  # Hardcoded as /suv/workspace/rule-set-library
INPUT_DIR = os.path.join(WORKSPACE_DIR, "in")  # Hardcoded as /suv/workspace/in
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "out")  # Hardcoded as /suv/workspace/out
TEST_DATA_DIR = os.path.join(BASE_DIR, "test_data")  # Directory for test files

# Java configuration
JAVA_HOME = os.environ.get("JAVA_HOME")
if not JAVA_HOME:
    JAVA_HOME = r"C:\PROGRA~1\Amazon\Corretto17"

JAVA = os.path.join(JAVA_HOME, "bin", "java")  # Match .bat with .exe

def delete_path(path):
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"Deleted: {path}")
    else:
        print(f"Path does not exist: {path}")

def zip_output_files(output_dir=OUTPUT_DIR):
    """Zip all files in the output directory and return as a BytesIO object."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zip_file.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

def run_command(command, capture_output=True):
    """Run a command from the /suv directory, optionally capturing output."""
    if capture_output:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=SUV_DIR,
        )
        # Log stdout
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                logger.info(f"Java stdout: {line.strip()}")

        # Log stderr
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            if line:
                logger.error(f"Java stderr: {line.strip()}")
    else:
        process = subprocess.Popen(command, cwd=SUV_DIR)

    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)

def run_validation(
    input_dir=INPUT_DIR,
    output_dir=OUTPUT_DIR,
    validation_gate="full",
    rule_set_dir=RULE_SET_DIR,
):


    validation_cmd = [
        JAVA,
        "-jar", os.path.join(rule_set_dir, "config", "rsl.jar"),
        "-i", f'"{input_dir}"',
        "-o", f'"{output_dir}"',
        "-vg", validation_gate,
        "-c", os.path.join(rule_set_dir, "config")
    ]

    # Construct the report generation command with quoted paths
    report_cmd = [
        JAVA,
        "-jar", os.path.join(rule_set_dir, "config", "qar2xlsx.jar"),
        f'{output_dir}'
    ]

    try:
        logger.info(f"Running validation with command: {' '.join(validation_cmd)}")
        run_command(validation_cmd, capture_output=True)  # Change to False to test without capture

        logger.info(f"Generating report with command: {' '.join(report_cmd)}")
        run_command(report_cmd, capture_output=True)  # Change to False to test without capture

        excel_files = [f for f in os.listdir(output_dir) if f.endswith('.xlsx')]
        if not excel_files:
            logger.error("No validation report generated")
            return None

        return zip_output_files(output_dir)

    except subprocess.CalledProcessError as e:
        logger.error(f"Validation failed with return code {e.returncode}")
        return None
    except FileNotFoundError as e:
        logger.error(f"File not found error: {e}")
        return None

def create_validation_context(validation_instance=None):

    if not validation_instance:
        validation_instance = str(uuid.uuid4())

    validation_base_path = os.path.join(WORKSPACE_DIR, f"temp_{validation_instance}")
    validation_input_path = os.path.join(validation_base_path, "in")
    validation_output_path = os.path.join(validation_base_path, "out")

    required_dirs = [validation_input_path, validation_output_path]
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            logger.warning(f"Required SUV directory not found: {dir_path}, creating it for test")
            os.makedirs(dir_path, exist_ok=True)

    return validation_base_path, validation_input_path, validation_output_path


if __name__ == "__main__":
    if not os.path.exists(TEST_DATA_DIR) or not os.listdir(TEST_DATA_DIR):
        logger.warning(f"No files found in {TEST_DATA_DIR}, skipping test")
    else:
        try:
            validation_base_path, validation_input_path, validation_output_path = create_validation_context()

            logger.info(f"Copying files from {TEST_DATA_DIR} to {validation_input_path}")
            for filename in os.listdir(TEST_DATA_DIR):
                src_path = os.path.join(TEST_DATA_DIR, filename)
                dst_path = os.path.join(validation_input_path, filename)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)

            result = run_validation(input_dir=validation_input_path, output_dir=validation_output_path)
            if result:
                logger.info(f"Validation successful, report generated at: {result}")
            else:
                logger.error("Validation failed or no report generated")

        except Exception as e:
            logger.error(f"Test failed: {e}")

        finally:
            logger.info(f"Test completed, input and output remain at {validation_input_path} and {validation_output_path}")