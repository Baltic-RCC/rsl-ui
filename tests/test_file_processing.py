import pytest
from unittest.mock import patch
from io import BytesIO
import zipfile
import validation_api


@pytest.fixture
def mock_fs(tmp_path):
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


def test_process_upload_regular_file(mock_fs):
    """Test uploading a regular file."""
    target_dir = mock_fs / "in"
    target_dir.mkdir(parents=True)

    filename = "test.xml"
    content = b"<xml>data</xml>"

    validation_api.process_upload(filename, content, target_dir)

    assert (target_dir / "test.xml").exists()
    assert (target_dir / "test.xml").read_bytes() == content


def test_process_upload_zip_extraction(mock_fs):
    """Test uploading and extracting a zip file."""
    target_dir = mock_fs / "in"
    target_dir.mkdir(parents=True)

    # Create a zip file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("model1.xml", b"content1")
        zf.writestr("subfolder/model2.xml", b"content2")
    zip_buffer.seek(0)

    validation_api.process_upload("models.zip", zip_buffer.read(), target_dir)

    # Check if extracted and flattened
    assert (target_dir / "model1.xml").exists()
    assert (target_dir / "model1.xml").read_bytes() == b"content1"

    # Check flattening (subfolder/model2.xml -> model2.xml)
    assert (target_dir / "model2.xml").exists()
    assert (target_dir / "model2.xml").read_bytes() == b"content2"

    # Ensure no subfolder created
    assert not (target_dir / "subfolder").exists()


def test_process_upload_zip_slip_protection(mock_fs):
    """Test that Zip Slip attempts are thwarted by flattening."""
    target_dir = mock_fs / "in"
    target_dir.mkdir(parents=True)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        # Malicious path
        zf.writestr("../../evil.txt", b"evil content")
    zip_buffer.seek(0)

    validation_api.process_upload("attack.zip", zip_buffer.read(), target_dir)

    # Should be flattened to "evil.txt" in target_dir
    assert (target_dir / "evil.txt").exists()

    # Should NOT be outside
    assert not (mock_fs / "evil.txt").exists()


def test_process_upload_invalid_zip(mock_fs):
    """Test handling of invalid zip files."""
    target_dir = mock_fs / "in"
    target_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="Invalid zip file"):
        validation_api.process_upload("bad.zip", b"not a zip", target_dir)
