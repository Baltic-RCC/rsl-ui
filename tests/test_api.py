import pytest
import json
import base64
from web_app import server
from unittest.mock import patch

@pytest.fixture
def client():
    server.config['TESTING'] = True
    with server.test_client() as client:
        yield client

def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json() == {"status": "healthy"}

@patch("validation_api.process_upload")
@patch("validation_api.create_validation_context")
def test_upload_files_api(mock_create_context, mock_process_upload, client):
    """Test the upload files API endpoint."""
    mock_create_context.return_value = ("base", "in", "out")
    
    upload_data = {
        "files": [
            {"name": "test1.xml", "content": base64.b64encode(b"<xml1/>").decode('utf-8')},
            {"name": "test2.xml", "content": base64.b64encode(b"<xml2/>").decode('utf-8')}
        ]
    }
    
    response = client.post('/upload_for_validation', 
                           data=json.dumps(upload_data),
                           content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert "validation_id" in data
    assert mock_process_upload.call_count == 2

def test_upload_files_api_invalid_json(client):
    """Test upload API with missing files key."""
    response = client.post('/upload_for_validation', 
                           data=json.dumps({"wrong_key": "data"}),
                           content_type='application/json')
    assert response.status_code == 400

@patch("validation_api.run_validation")
@patch("validation_api.create_validation_context")
@patch("validation_api.clean_dir")
def test_validate_endpoint(mock_clean, mock_create, mock_run, client):
    """Test the validate endpoint with and without validation_gate."""
    mock_create.return_value = ("base", "in", "out")
    mock_run.return_value = ["Log 1", "Log 2"]
    
    # 1. Without gate (default)
    response = client.get('/validate/test-id')
    assert response.status_code == 200
    assert "Log 1\nLog 2" in response.get_data(as_text=True)
    mock_run.assert_called_with("in", "out", validation_gate="full")
    
    # 2. With valid gate
    response = client.get('/validate/test-id?validation_gate=full_igm')
    assert response.status_code == 200
    mock_run.assert_called_with("in", "out", validation_gate="full_igm")

    # 3. With invalid gate
    mock_run.return_value = ["Invalid validation gate: ..."]
    response = client.get('/validate/test-id?validation_gate=invalid')
    assert response.status_code == 200 # It returns the logs even if gate is invalid
    assert "Invalid validation gate" in response.get_data(as_text=True)

@patch("validation_api.download_validation_results")
@patch("validation_api.create_validation_context")
def test_download_results_endpoint(mock_create, mock_download, client):
    """Test the download results endpoint."""
    from io import BytesIO
    mock_create.return_value = ("base", "in", "out")
    mock_download.return_value = BytesIO(b"dummy zip content")
    
    response = client.get('/download_results/test-id')
    assert response.status_code == 200
    assert response.mimetype == 'application/zip'
    assert b"dummy zip content" in response.data
