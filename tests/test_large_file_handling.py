import pytest
from io import BytesIO
import zipfile
import validation_api
from unittest.mock import patch


@pytest.fixture
def mock_fs_large(tmp_path):
    """Fixture to mock file system paths."""
    with (
        patch("validation_api.WORKSPACE_DIR", str(tmp_path / "workspace")),
        patch("validation_api.SUV_DIR", str(tmp_path)),
        patch(
            "validation_api.RULE_SET_DIR",
            str(tmp_path / "workspace" / "rule-set-library"),
        ),
    ):
        yield tmp_path


def test_process_large_zip_file(mock_fs_large):
    """
    Test processing a 'large' zip file (simulated).
    We create a zip file with a 50MB dummy file to ensure logic handles
    sizes larger than default chunks.
    """
    target_dir = mock_fs_large / "in"
    target_dir.mkdir(parents=True)

    # Create a dummy large file (50MB)
    # Using a repeatable pattern so it compresses well, keeping test fast
    large_data = b"0" * (50 * 1024 * 1024)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("large_model.xml", large_data)

    zip_buffer.seek(0)

    # Process it
    # Note: process_upload currently takes bytes, which loads strict 2GB limit
    # into RAM. This test confirms that at least for 50MB it works.
    validation_api.process_upload("large.zip", zip_buffer.read(), target_dir)

    extracted_file = target_dir / "large_model.xml"
    assert extracted_file.exists()
    assert extracted_file.stat().st_size == len(large_data)


def test_process_many_files_in_zip(mock_fs_large):
    """Test processing a zip with many small files (stress test extraction)."""
    target_dir = mock_fs_large / "in"
    target_dir.mkdir(parents=True)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for i in range(100):
            zf.writestr(f"folder/model_{i}.xml", f"<data>{i}</data>")

    zip_buffer.seek(0)

    validation_api.process_upload("many.zip", zip_buffer.read(), target_dir)

    # Check if all 100 files are extracted and flattened
    count = 0
    for item in target_dir.iterdir():
        if item.name.startswith("model_") and item.suffix == ".xml":
            count += 1

    assert count == 100
