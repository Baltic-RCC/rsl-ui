import os
import shutil
import subprocess
import logging
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
import xml.etree.ElementTree as etree

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

def clean_dir(dir: Path):
    for item in dir.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

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
    validation_log = []
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
                logger.info(f"{line.strip()}")
                validation_log.append(line)

        # Log stderr
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            if line:
                logger.info(f"{line.strip()}")
                validation_log.append(line)
    else:
        process = subprocess.Popen(command, cwd=SUV_DIR)

    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)

    return validation_log

def run_validation(
    input_dir=INPUT_DIR,
    output_dir=OUTPUT_DIR,
    validation_gate="full",
    rule_set_dir=RULE_SET_DIR,
):

    validation_log = []

    validation_cmd = [
        JAVA,
        "-jar", os.path.join(rule_set_dir, "config", "rsl.jar"),
        "-i", f'"{input_dir}"',
        "-o", f'"{output_dir}"',
        "-vg", validation_gate,
        "-c", os.path.join(rule_set_dir, "config")
    ]

    # Construct the report generation command
    report_cmd = [
        JAVA,
        "-jar", os.path.join(rule_set_dir, "config", "qar2xlsx.jar"),
        f'{output_dir}'
    ]

    try:
        logger.info(f"Running validation with command: {' '.join(validation_cmd)}")
        validation_log.extend(run_command(validation_cmd, capture_output=True))  # Change to False to test without capture
    except subprocess.CalledProcessError as e:
        error_text = f"Validation failed: {e.returncode}"
        logger.error(error_text)
        validation_log.extend(error_text)
        return None

    try:
        logger.info(f"Generating report with command: {' '.join(report_cmd)}")
        validation_log.extend(run_command(report_cmd, capture_output=True))  # Change to False to test without capture
    except subprocess.CalledProcessError as e:
        error_text = [f"Excel Report generation failed: {e.returncode, e.output}", "Make sure that confgi/qar2xslx.jar is in RSL ZIP"]
        logger.error(error_text)
        validation_log.extend(error_text)

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
            logger.warning(f"Required SUV directory not found: {dir_path}, creating it for test")
            os.makedirs(dir_path, exist_ok=True)

    return validation_base_path, validation_input_path, validation_output_path

def get_ruleset_version():
    try:
        tree = etree.parse(os.path.join(RULE_SET_DIR, 'config', 'config.xml'))
        root = tree.getroot()
        rsl_version = root.find('{http://entsoe.eu/CIM/Extensions/CGM-BP/2020#}rslVersion').text
        return rsl_version
    except:
        return None


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
        with zipfile.ZipFile(rsl_zip_bytes, 'r') as zip_ref:
            # Get the list of files/folders in the zip
            zip_contents = zip_ref.namelist()

            # Find the first internal folder (assuming it's the common prefix)
            if not zip_contents:
                raise ValueError("Zip file is empty")

            # Determine the root folder (first common prefix)
            root_folder = os.path.commonprefix(zip_contents)
            if not root_folder or not root_folder.endswith('/'):
                raise ValueError("Zip file does not contain a single root folder")

            # Strip the root folder and extract contents
            for file_info in zip_ref.infolist():
                # Skip directories and files outside the root folder
                if file_info.filename.startswith(root_folder) and not file_info.is_dir():
                    # Remove the root folder prefix from the file path
                    relative_path = file_info.filename[len(root_folder):]
                    if relative_path:  # Ensure there's a remaining path after stripping
                        target_path = rule_set_dir / relative_path
                        # Ensure the target directory exists
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        # Extract the file to the target path
                        with zip_ref.open(file_info) as source, open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)

        logger.info("RSL updated successfully from in-memory zip data, stripped root folder")
    except Exception as e:
        logger.error(f"Failed to update RSL: {str(e)}")
        raise


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