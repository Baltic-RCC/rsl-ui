# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import datetime
import uuid
import dash
import logging
from flask import Flask, send_file, request, jsonify
from flasgger import Swagger, swag_from
from pathlib import Path

import validation_api
from layout import create_layout
from callbacks import register_callbacks
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app_version = Config.APP_VERSION

# Initialise flask
server = Flask(__name__)
# Load secret key
if "FLASK_SECRET_KEY" not in os.environ:
    logger.warning(
        "WARNING: FLASK_SECRET_KEY not set. Using default insecure key. Sessions will persist but are not secure."
    )
server.secret_key = Config.FLASK_SECRET_KEY
# Set max content length to allow large uploads
server.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

# Initialize dash single page app
# Dash automatically serves files from 'assets/' folder, including bootstrap.min.css and custom.css
app = dash.Dash(
    __name__,
    server=server,
    title="CGMES Validator",
)

# Initialize Flasgger with Swagger UI for API documentation
swagger = Swagger(
    server,
    template={
        "info": {
            "title": "CGMES Validator API",
            "description": "REST API for validating CGMES files and managing validation results",
            "version": app_version,
        },
        "basePath": "/",
    },
)

# Load SVG logo (with fallback if not available)
with open("assets/logo.svg", "r") as f:
    svg_logo = f.read()

# Override the default HTML to set body margin to 0
# Custom index string with sticky footer
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer class="bg-light text-center py-2 border-top mt-3">
            <p><a href="/apidocs" target="_blank">API Documentation</a></p>
        </footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </body>
</html>
"""

# Set Layout
app.layout = create_layout(app_version, svg_logo)

# Register Callbacks
register_callbacks(app, app_version)


@server.route("/validate/<validation_instance>")
@swag_from(
    {
        "tags": ["Validation"],
        "parameters": [
            {
                "name": "validation_instance",
                "in": "path",
                "type": "string",
                "required": True,
                "description": "Unique validation instance ID (UUID)",
            },
            {
                "name": "validation_gate",
                "in": "query",
                "type": "string",
                "required": False,
                "default": "full",
                "enum": ["full", "full_igm", "full_cgm", "bds"],
                "description": "Validation gate to use",
            },
        ],
        "responses": {
            "200": {
                "description": "Validation result as plain text",
                "schema": {"type": "string"},
            },
            "500": {"description": "Validation failed"},
        },
    }
)
def validate_api_endpoint(validation_instance):
    validation_gate = request.args.get("validation_gate", "full")
    _, input_dir, output_dir = validation_api.prepare_session(validation_instance)
    validation_api.clean_dir(Path(output_dir))
    result = validation_api.run_validation(
        input_dir, output_dir, validation_gate=validation_gate
    )
    if result:
        return "\n".join(result) if isinstance(result, list) else result
    return "Validation failed", 500


@server.route("/download_results/<validation_instance>")
@swag_from(
    {
        "tags": ["Validation"],
        "parameters": [
            {
                "name": "validation_instance",
                "in": "path",
                "type": "string",
                "required": True,
                "description": "Unique validation instance ID (UUID)",
            }
        ],
        "responses": {
            "200": {
                "description": "ZIP file containing validation results",
                "content": {
                    "application/zip": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                },
            },
            "500": {"description": "Validation failed"},
        },
    }
)
def download_file(validation_instance):
    _, _, output_dir = validation_api.prepare_session(validation_instance)
    result = validation_api.download_validation_results(output_dir)
    if result:
        return send_file(
            result,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"validation_results_{datetime.datetime.now():%Y%m%dT%H%M}.zip",
        )
    return "Validation failed", 500


@server.route("/upload_for_validation", methods=["POST"])
@swag_from(
    {
        "tags": ["Validation"],
        "summary": "Upload files for validation",
        "consumes": ["application/json"],
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Filename",
                                    },
                                    "content": {
                                        "type": "string",
                                        "description": "Base64-encoded file content",
                                    },
                                },
                                "required": ["name", "content"],
                            },
                        }
                    },
                    "required": ["files"],
                },
            }
        ],
        "responses": {
            "200": {
                "description": "Files uploaded successfully",
                "schema": {
                    "type": "object",
                    "properties": {
                        "validation_id": {
                            "type": "string",
                            "description": "Unique ID for this validation session",
                        }
                    },
                },
            },
            "400": {"description": "Missing 'files' in request"},
            "500": {"description": "Failed to process a file"},
        },
    }
)
def upload_files_api():
    data = request.get_json()
    if not data or "files" not in data:
        return jsonify({"error": "Missing 'files' in request"}), 400

    # Create unique context
    validation_id = str(uuid.uuid4())
    _, input_dir, _ = validation_api.prepare_session(validation_id)

    # Store each file
    for file in data["files"]:
        try:
            validation_api.save_base64_upload(file["name"], file["content"], input_dir)
        except Exception as e:
            return jsonify(
                {
                    "error": f"Failed to process file '{file.get('name', 'unknown')}': {str(e)}"
                }
            ), 500

    return jsonify({"validation_id": validation_id}), 200


@server.route("/health")
def health_check():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
