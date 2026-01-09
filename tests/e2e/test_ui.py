import threading
import time
import pytest
import re
from playwright.sync_api import Page, expect
from web_app import app
from pathlib import Path
import zipfile

# Define a port for the test server
TEST_PORT = 8051
BASE_URL = f"http://localhost:{TEST_PORT}"


def run_server():
    """Run the Dash app server in a separate thread."""
    # Suppress startup output
    app.run(host="127.0.0.1", port=TEST_PORT, debug=False, use_reloader=False)


@pytest.fixture(scope="module", autouse=True)
def start_server():
    """Start the server before tests and stop after."""
    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()

    # Wait for server to start
    time.sleep(2)
    yield
    # Thread will be killed when main process exits (daemon=True)


@pytest.fixture(autouse=True)
def clean_rsl_state():
    """Ensure a clean RSL state before each test."""
    # We need to access the module variable, but since we are in a separate process/file,
    # we must rely on filesystem cleaning.
    # The app uses 'suv/workspace/rule-set-library' relative to validation_api.py location.

    # We can assume the default location relative to the current working directory
    # since we run pytest from root.
    rsl_dir = Path("suv/workspace/rule-set-library")
    if rsl_dir.exists():
        import shutil

        shutil.rmtree(rsl_dir)

    yield

    # Optional cleanup after
    if rsl_dir.exists():
        import shutil

        shutil.rmtree(rsl_dir)


def test_page_loads(page: Page):
    """Test that the page loads correctly."""
    page.goto(BASE_URL)

    # Check title
    expect(page).to_have_title("CGMES Validator")

    # Check for header
    expect(page.locator("h1")).to_have_text("Validator UI")


def test_console_no_errors(page: Page):
    """Test that there are no console errors on load."""
    console_errors = []
    page.on(
        "console",
        lambda msg: console_errors.append(msg) if msg.type == "error" else None,
    )

    page.goto(BASE_URL)

    # Wait a bit for any async scripts (Dash)
    page.wait_for_timeout(1000)

    assert len(console_errors) == 0, f"Found console errors: {console_errors}"


def test_upload_components_exist(page: Page):
    """Test that upload components are present and in correct initial state."""
    page.goto(BASE_URL)

    # Check for main file upload
    expect(page.locator("#upload-data")).to_be_visible()

    # Check for buttons
    btn_validate = page.locator("#btn-validate")
    expect(btn_validate).to_be_visible()
    # Should be disabled initially
    expect(btn_validate).to_be_disabled()

    expect(page.locator("#btn-delete-all")).to_be_visible()


def test_rsl_version_display(page: Page):
    """Test that RSL version is displayed (or Not Loaded)."""
    page.goto(BASE_URL)
    expect(page.locator("#rsl-version")).to_be_visible()
    expect(page.locator("#rsl-version")).to_contain_text("App:")


def test_upload_single_xml_file(page: Page, tmp_path):
    """Test uploading a single XML file."""
    page.goto(BASE_URL)

    # Create a dummy XML file
    file_path = tmp_path / "test_model.xml"
    file_path.write_text("<rdf:RDF></rdf:RDF>")

    # Upload file (target the input inside the dcc.Upload component)
    page.locator("#upload-data input[type=file]").set_input_files(str(file_path))

    # Verify the filename appears in the file list
    expect(page.locator("#folder-content")).to_contain_text("test_model.xml")


def test_upload_zip_extraction(page: Page, tmp_path):
    """
    Test uploading a ZIP file containing nested models.
    Verifies that the UI shows the extracted (flattened) files.
    """
    page.goto(BASE_URL)

    # Create a zip file with nested structure
    zip_path = tmp_path / "models.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("model1.xml", "<data>1</data>")
        zf.writestr("nested/model2.xml", "<data>2</data>")

    # Upload the zip file
    page.locator("#upload-data input[type=file]").set_input_files(str(zip_path))

    # Verify both files appear in the list (flattened)
    folder_content = page.locator("#folder-content")
    expect(folder_content).to_contain_text("model1.xml")
    expect(folder_content).to_contain_text("model2.xml")

    # Strict check:
    content_text = folder_content.inner_text()
    assert "model1.xml" in content_text
    assert "model2.xml" in content_text


def test_upload_mixed_files(page: Page, tmp_path):
    """Test uploading a mix of XML and ZIP files."""
    page.goto(BASE_URL)

    xml_path = tmp_path / "extra.xml"
    xml_path.write_text("<data>3</data>")

    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("inside_zip.xml", "<data>4</data>")

    # Upload both files at once
    page.locator("#upload-data input[type=file]").set_input_files(
        [str(xml_path), str(zip_path)]
    )

    # Verify all files are listed
    folder_content = page.locator("#folder-content")
    expect(folder_content).to_contain_text("extra.xml")
    expect(folder_content).to_contain_text("inside_zip.xml")


def test_bootstrap_and_validate(page: Page, tmp_path):
    """
    Test the full lifecycle:
    1. Verify System Not Ready state
    2. Upload RSL (Bootstrap)
    3. Verify System Ready state
    4. Upload Model & Validate
    """
    page.goto(BASE_URL)

    # 1. Verify Initial State
    # Alert should show "System Not Ready"
    alert = page.locator("#system-status-alert")
    expect(alert).to_be_visible()
    expect(alert).to_contain_text("System Not Ready")

    # Validate button disabled
    expect(page.locator("#btn-validate")).to_be_disabled()

    # RSL Accordion should be auto-expanded (class 'show' usually, or check visibility of inner element)
    # The 'item-0' logic in callback ensures it's active.
    # We can check if the upload-rsl component is visible without clicking.
    expect(page.locator("#upload-rsl")).to_be_visible()

    # 2. Create dummy RSL
    rsl_zip = tmp_path / "rsl.zip"
    with zipfile.ZipFile(rsl_zip, "w") as zf:
        zf.writestr(
            "rsl-v1/config/config.xml",
            '<?xml version="1.0"?><rsl><entsoe:rslVersion xmlns:entsoe="http://entsoe.eu/CIM/Extensions/CGM-BP/2020#">TEST-1.0</entsoe:rslVersion></rsl>',
        )
        zf.writestr("rsl-v1/config/rsl.jar", "dummy jar")
        zf.writestr("rsl-v1/config/qar2xlsx.jar", "dummy report jar")

    # 3. Upload RSL
    page.locator("#upload-rsl input[type=file]").set_input_files(str(rsl_zip))

    # 4. Verify Ready State
    # Alert should change to "System Ready"
    expect(alert).to_contain_text("System Ready")
    # Button should enable
    expect(page.locator("#btn-validate")).to_be_enabled()
    # Version header updated
    expect(page.locator("#rsl-version")).to_contain_text("TEST-1.0")

    # 5. Upload Model & Validate
    sample_file = Path("test_data/Sample_Model_EQ.xml").absolute()
    page.locator("#upload-data input[type=file]").set_input_files(str(sample_file))

    page.locator("#btn-validate").click()

    # Expect failure.
    # Use regex to match any of the valid failure modes (Java missing or Bad Jar)
    result_area = page.locator("#validation-result")
    expect(result_area).to_be_visible()

    # This will retry until the text matches the pattern
    expect(result_area).to_contain_text(
        re.compile(
            r"Invalid or corrupt jarfile|Executable not found|Validation JAR not found"
        )
    )


def test_validation_execution(page: Page, tmp_path):
    """
    Test the validation flow using a real sample model.
    Must bootstrap first.
    """
    page.goto(BASE_URL)

    # Bootstrap
    rsl_zip = tmp_path / "rsl.zip"
    with zipfile.ZipFile(rsl_zip, "w") as zf:
        zf.writestr(
            "rsl-v1/config/config.xml",
            '<?xml version="1.0"?><rsl><entsoe:rslVersion xmlns:entsoe="http://entsoe.eu/CIM/Extensions/CGM-BP/2020#">TEST-1.0</entsoe:rslVersion></rsl>',
        )
        zf.writestr("rsl-v1/config/rsl.jar", "dummy jar")
        zf.writestr("rsl-v1/config/qar2xlsx.jar", "dummy report jar")

    page.locator("#upload-rsl input[type=file]").set_input_files(str(rsl_zip))
    expect(page.locator("#btn-validate")).to_be_enabled()

    # Use the sample file
    sample_file = Path("test_data/Sample_Model_EQ.xml").absolute()
    page.locator("#upload-data input[type=file]").set_input_files(str(sample_file))

    # Click Validate
    page.locator("#btn-validate").click()

    # Wait for result area
    result_area = page.locator("#validation-result")
    expect(result_area).to_be_visible()

    # Check for expected error (backend execution attempt)
    expect(result_area).to_contain_text(
        re.compile(r"Invalid or corrupt jarfile|Executable not found")
    )
