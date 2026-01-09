import os


class Config:
    APP_VERSION = "0.1.3"
    FLASK_SECRET_KEY = os.environ.get(
        "FLASK_SECRET_KEY", "default-insecure-secret-key-change-me"
    )
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024  # 5GB

    # Validation
    VALIDATION_TIMEOUT = int(os.environ.get("VALIDATION_TIMEOUT", 1200))
    PROGRESS_POLL_INTERVAL_MS = 1000

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SUV_DIR = os.environ.get("SUV_DIR", os.path.join(BASE_DIR, "suv"))
    WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", os.path.join(SUV_DIR, "workspace"))
    RULE_SET_DIR = os.environ.get(
        "RULE_SET_DIR", os.path.join(WORKSPACE_DIR, "rule-set-library")
    )
    TEST_DATA_DIR = os.path.join(BASE_DIR, "test_data")

    # Java
    JAVA_HOME = os.environ.get("JAVA_HOME")
