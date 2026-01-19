# Validator UI

UI for ENTSO-E CGMES validation tool. 

## Key Features
- **Secure File Handling**: Safe ZIP extraction with "Zip Slip" protection and filename sanitization.
- **Extreme Resilience**: Production-ready deployment with Gunicorn, high timeouts (20m), and health checks.
- **Bootstrapping Workflow**: Upload your Rule Set Library (RSL) directly via the UI to configure the validation engine.
- **OWASP Compliant**: Hardened against XXE, Command Injection, and Path Traversal.
- **Comprehensive Testing**: Full suite of Unit, Security, and Playwright E2E tests.

## Validation Gates
The validator supports the following gates:
- **Full**: Standard validation.
- **Full IGM**: Validation optimized for Individual Grid Models.
- **Full CGM**: Validation optimized for Common Grid Models.
- **BDS**: Basic Data Structure validation.

## Prerequisites
- **Java**: Java 17+ (e.g., Eclipse Temurin) must be installed on the host or in the container.
- **Python**: 3.12+

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_SECRET_KEY` | **Required for Production.** Secret key for signing session cookies. | `default-insecure...` |
| `SUV_DIR` | Directory for the Standalone Validation Tool. | `./suv` |
| `JAVA_HOME` | Path to Java installation. | (System Default) |

## Local Installation
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python web_app.py
   ```
   Access at `http://localhost:8050`.

## Docker / Podman Installation
Build and run the production image:
```bash
podman build -t rsl-ui:0.1.6 .
podman run -d -p 8050:8050 --name rsl-ui rsl-ui:0.1.6
```

## First Time Setup (Bootstrapping)
1. Open the UI at `http://localhost:8050`.
2. You will see a **"System Not Ready"** warning.
3. Open the **"Upload RSL"** section.
4. Upload your RSL ZIP file (must contain `config/rsl.jar` and `config/qar2xlsx.jar`).
5. Once uploaded, the system status will turn **Green**, and validation will be enabled.

## Development & Testing
Install development requirements:
```bash
pip install -r requirements-dev.txt
playwright install chromium
```

Run the full test suite:
```bash
PYTHONPATH=. pytest tests/
```

Run linting and formatting (Ruff):
```bash
ruff check .
ruff format .
```

## API Documentation
The application includes a Swagger UI for REST API interaction, available at `/apidocs`.

## License
This project is licensed under the Mozilla Public License Version 2.0. See the [LICENSE](LICENSE) file for details.