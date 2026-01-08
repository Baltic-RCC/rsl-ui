import os
import datetime

import dash
from dash.dependencies import Input, Output, State
from dash import dcc, html, no_update
import dash_bootstrap_components as dbc
from flask import Flask, send_file, session, request, jsonify
from flasgger import Swagger, swag_from

from io import BytesIO
import base64
import uuid
import validation_api
from dash import ctx

# import pandas as pd

from pathlib import Path

app_version = "0.1.2"


def get_or_create_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


# Initialise flask
server = Flask(__name__)
# Load secret key from environment variable or use a fixed default
# Using a fixed default ensures session consistency across Gunicorn workers
if "FLASK_SECRET_KEY" not in os.environ:
    print("WARNING: FLASK_SECRET_KEY not set. Using default insecure key. Sessions will persist but are not secure.")
server.secret_key = os.environ.get("FLASK_SECRET_KEY", "default-insecure-secret-key-change-me")
# Set max content length to 5GB to allow large uploads
server.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024 * 1024

# Initialize dash single page app
external_stylesheets = ["assets/bootstrap.min.css"]
app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=external_stylesheets,
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

# App layout with header and fixes
app.layout = html.Div(
    style={
        "margin": "0",  # Remove default margin to eliminate white border
        "padding": "0",
        "minHeight": "100vh",  # Ensure full height
        "boxSizing": "border-box",
    },
    children=[
        # Header with black background
        html.Div(
            style={
                "backgroundColor": "#000000",  # Black background
                "padding": "10px",
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "color": "#ffffff",  # White text
                "margin": "0",  # Ensure no margin
                "width": "100%",  # Full width
                "boxSizing": "border-box",
            },
            children=[
                # Left side: Logo and App Name
                html.Div(
                    style={"display": "flex", "alignItems": "center"},
                    children=[
                        html.Img(
                            src=f"data:image/svg+xml;base64,{base64.b64encode(svg_logo.encode('utf-8')).decode('utf-8')}",
                            style={"height": "40px", "marginRight": "10px"},
                        ),
                        html.H1(
                            "Validator UI", style={"fontSize": "24px", "margin": "0"}
                        ),
                    ],
                ),
                # Right side: Swagger Button and RSL Version
                html.Div(
                    style={"display": "flex", "alignItems": "center"},
                    children=[
                        html.A(
                            "Swagger API",
                            href="/apidocs",
                            target="_blank",
                            className="btn btn-outline-light btn-sm me-3",
                            role="button",
                        ),
                        html.Div(
                            id="rsl-version",
                            children=f"App: {app_version}        RSL: {validation_api.get_ruleset_version()}",
                            style={"fontSize": "18px"},
                        ),
                    ],
                ),
            ],
        ),
        # Main content with constrained width
        html.Div(
            style={
                "maxWidth": "1200px",  # Constrain content width
                "margin": "0 auto",  # Center content
                "padding": "20px",
                "boxSizing": "border-box",
            },
            children=[
                dcc.Location(id="page-state", refresh=False),
                # System Status Alert
                dbc.Alert(
                    id="system-status-alert",
                    dismissable=False,
                    is_open=True,
                    fade=True,
                ),
                # RSL Configuration (Bootstrap) - Now at the Top
                dbc.Accordion(
                    id="rsl-accordion",
                    children=[
                        dbc.AccordionItem(
                            title="Upload RSL",
                            children=[
                                dcc.Upload(
                                    id="upload-rsl",
                                    children=html.Div(
                                        [
                                            "Drag and Drop or ",
                                            html.A("Select RSL Zip File"),
                                        ]
                                    ),
                                    style={
                                        "width": "100%",
                                        "height": "60px",
                                        "lineHeight": "60px",
                                        "borderWidth": "1px",
                                        "borderStyle": "dashed",
                                        "borderRadius": "5px",
                                        "textAlign": "center",
                                        "margin": "10px 0",
                                        "boxSizing": "border-box",
                                    },
                                    multiple=False,
                                ),
                                html.Div(id="rsl-upload-status"),
                            ],
                        ),
                    ],
                    start_collapsed=True,
                    className="mb-3",
                ),
                # Validation Controls
                html.Div(
                    [
                        html.Label("Validation Gate:", className="me-2"),
                        dcc.Dropdown(
                            id="validation-gate-dropdown",
                            options=[
                                {"label": "Full", "value": "full"},
                                {"label": "Full IGM", "value": "full_igm"},
                                {"label": "Full CGM", "value": "full_cgm"},
                            ],
                            value="full",
                            clearable=False,
                            style={"width": "200px", "display": "inline-block"},
                            disabled=True,
                        ),
                    ],
                    className="mb-3 d-flex align-items-center",
                ),
                dbc.Button(
                    "Validate",
                    id="btn-validate",
                    color="primary",
                    className="me-1",
                    outline=True,
                    disabled=True,
                ),
                dbc.Button(
                    "Delete All",
                    id="btn-delete-all",
                    color="danger",
                    className="me-1",
                    outline=True,
                ),
                dbc.Button(
                    "Delete All but BDS",
                    id="btn-delete-all-keep-bds",
                    color="warning",
                    className="me-1",
                    outline=True,
                ),
                dcc.Upload(
                    id="upload-data",
                    children=html.Div(
                        [
                            "Drag and Drop or ",
                            html.A("Select Files"),
                            " for validation.",
                        ]
                    ),
                    style={
                        "width": "100%",
                        "height": "60px",
                        "lineHeight": "60px",
                        "borderWidth": "1px",
                        "borderStyle": "dashed",
                        "borderRadius": "5px",
                        "textAlign": "center",
                        "margin": "10px 0",
                        "boxSizing": "border-box",
                    },
                    multiple=True,
                ),
                html.Div(id="uploaded-files"),
                html.Div(id="folder-content"),
                html.Div(id="download-validation-result"),
                html.Div(
                    id="validation-result",
                    children=None,
                    style={
                        "maxHeight": "700px",
                        "overflowY": "auto",
                        "backgroundColor": "#f8f9fa",
                        "padding": "10px",
                        "border": "1px solid #ddd",
                        "borderRadius": "5px",
                        "marginTop": "20px",
                        "fontFamily": "monospace",
                        "fontSize": "14px",
                    },
                ),
            ],
        ),
    ],
)


def get_file_list_ui(model_input):
    return [
        html.Li(item.name) for item in Path(model_input).glob("*") if not item.is_dir()
    ]


@app.callback(
    Output("folder-content", "children"),
    Input("page-state", "pathname"),  # triggers on load/refresh
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    Input("btn-delete-all", "n_clicks"),
    Input("btn-delete-all-keep-bds", "n_clicks"),
)
def manage_files(
    pathname, upload_contents, upload_names, delete_clicks, keep_bds_clicks
):
    _, model_input, model_output = validation_api.create_validation_context(
        get_or_create_session_id()
    )

    triggered_id = ctx.triggered_id
    if triggered_id == "upload-data" and upload_contents:
        for name, content in zip(upload_names, upload_contents):
            content_string = content.split(",")[1]
            decoded = base64.b64decode(content_string)
            validation_api.process_upload(name, decoded, model_input)

        return get_file_list_ui(model_input)

    elif triggered_id == "btn-delete-all" and delete_clicks:
        validation_api.clean_dir(Path(model_input))
        validation_api.clean_dir(Path(model_output))

        return get_file_list_ui(model_input)

    elif triggered_id == "btn-delete-all-keep-bds" and keep_bds_clicks:
        validation_api.clean_dir(Path(model_output))

        for item in Path(model_input).glob("*"):
            if item.is_file() and "BD_" not in item.name:
                item.unlink()

        return get_file_list_ui(model_input)

    if triggered_id == "page-state":
        return get_file_list_ui(model_input)

    return no_update


@app.callback(
    Output("download-validation-result", "children"),
    Output("validation-result", "children"),
    Input("btn-validate", "n_clicks"),
    State("validation-gate-dropdown", "value"),
)
def validate(n_clicks, validation_gate):
    if n_clicks:
        session_id = get_or_create_session_id()
        _, input_dir, output_dir = validation_api.create_validation_context(
            get_or_create_session_id()
        )
        validation_api.clean_dir(Path(output_dir))
        validation_result = validation_api.run_validation(
            input_dir, output_dir, validation_gate=validation_gate
        )

        log_display = [html.Div(line) for line in validation_result]
        download_link = html.A(
            "Download validation results",
            href=f"/download_results/{session_id}",
            target="_blank",
        )

        return download_link, log_display

    else:
        return no_update, no_update


@app.callback(
    Output("rsl-upload-status", "children"),
    Output("rsl-version", "children"),
    Output("btn-validate", "disabled"),
    Output("validation-gate-dropdown", "disabled"),
    Output("system-status-alert", "children"),
    Output("system-status-alert", "color"),
    Output("rsl-accordion", "active_item"),
    Input("upload-rsl", "contents"),
    Input("page-state", "pathname"),
    State("upload-rsl", "filename"),
)
def update_rsl_and_status(contents, pathname, filename):
    triggered_id = ctx.triggered_id

    # Handle RSL Upload
    upload_msg = None
    if triggered_id == "upload-rsl" and contents is not None:
        if filename.endswith(".zip"):
            content_string = contents.split(",")[1]
            decoded = base64.b64decode(content_string)
            rsl_zip_bytes = BytesIO(decoded)
            try:
                validation_api.update_rsl(rsl_zip_bytes)
                new_version = validation_api.get_ruleset_version()
                upload_msg = html.Span(
                    f"RSL updated successfully to version {new_version}",
                    style={"color": "green"},
                )
            except Exception as e:
                upload_msg = html.Span(
                    f"Failed to update RSL: {str(e)}", style={"color": "red"}
                )
        else:
            upload_msg = html.Span(
                "Please upload a valid .zip file", style={"color": "red"}
            )

    # Check Configuration State
    is_ready = validation_api.is_configured()
    current_version = validation_api.get_ruleset_version()

    version_text = (
        f"App: {app_version}        RSL: {current_version}"
        if current_version
        else f"App: {app_version}        RSL: Not Loaded"
    )

    if is_ready:
        status_text = "System Ready: RSL loaded."
        status_color = "success"
        btn_disabled = False
        dropdown_disabled = False
        accordion_state = None  # Collapse
    else:
        status_text = (
            "System Not Ready: Please upload RSL (Zip file) to enable validation."
        )
        status_color = "warning"
        btn_disabled = True
        dropdown_disabled = True
        accordion_state = "item-0"  # Expand the first item (Upload RSL)

    return (
        upload_msg,
        version_text,
        btn_disabled,
        dropdown_disabled,
        status_text,
        status_color,
        accordion_state,
    )


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
                "enum": ["full", "full_igm", "full_cgm"],
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
    _, input_dir, output_dir = validation_api.create_validation_context(
        validation_instance
    )
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
    _, _, output_dir = validation_api.create_validation_context(validation_instance)
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
    _, input_dir, _ = validation_api.create_validation_context(validation_id)

    # Store each file
    for file in data["files"]:
        try:
            content = base64.b64decode(file["content"])
            validation_api.process_upload(file["name"], content, input_dir)
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