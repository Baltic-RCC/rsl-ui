import os
import json
import uuid
from pathlib import Path
from typing import List, Tuple, Optional, Any, Union, Dict

from flask import session
from dash import Input, Output, State, ctx, no_update, html, Dash
import validation_api


def get_or_create_session_id() -> str:
    """Retrieves the current session ID or creates a new one if it doesn't exist."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


def get_file_list_ui(model_input: str) -> List[html.Li]:
    """Generates the UI list of files in the input directory."""
    return [
        html.Li(item.name) for item in Path(model_input).glob("*") if not item.is_dir()
    ]


def register_callbacks(app: Dash, app_version: str) -> None:
    """
    Registers all Dash callbacks for the application.

    Args:
        app: The Dash application instance.
        app_version: The version string of the application.
    """

    @app.callback(
        Output("folder-content", "children"),
        Input("page-state", "pathname"),
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
        Input("btn-delete-all", "n_clicks"),
        Input("btn-delete-all-keep-bds", "n_clicks"),
    )
    def manage_files(
        pathname: Optional[str],
        upload_contents: Optional[List[str]],
        upload_names: Optional[List[str]],
        delete_clicks: Optional[int],
        keep_bds_clicks: Optional[int],
    ) -> Union[List[html.Li], Any]:
        """
        Handles file uploads and deletions in the workspace.
        Delegates storage logic to validation_api.
        """
        _, model_input, model_output = validation_api.prepare_session(
            get_or_create_session_id()
        )

        triggered_id = ctx.triggered_id

        if triggered_id == "upload-data" and upload_contents and upload_names:
            for name, content in zip(upload_names, upload_contents):
                validation_api.save_base64_upload(name, content, model_input)
            return get_file_list_ui(model_input)

        elif triggered_id == "btn-delete-all" and delete_clicks:
            validation_api.reset_workspace(model_input, model_output)
            return get_file_list_ui(model_input)

        elif triggered_id == "btn-delete-all-keep-bds" and keep_bds_clicks:
            validation_api.reset_workspace(
                model_input, model_output, keep_pattern="BD_"
            )
            return get_file_list_ui(model_input)

        if triggered_id == "page-state":
            return get_file_list_ui(model_input)

        return no_update

    @app.callback(
        Output("progress-interval", "disabled", allow_duplicate=True),
        Output("btn-validate", "disabled", allow_duplicate=True),
        Output("validation-progress", "value", allow_duplicate=True),
        Output("validation-progress", "label"),
        Output("validation-progress", "style"),
        Input("btn-validate", "n_clicks"),
        State("validation-gate-dropdown", "value"),
        prevent_initial_call=True,
    )
    def start_validation(
        n_clicks: Optional[int], validation_gate: str
    ) -> Tuple[bool, bool, int, str, Dict[str, str]]:
        """
        Initiates the validation process in the background.
        """
        if not n_clicks:
            return no_update

        session_id = get_or_create_session_id()
        _, input_dir, output_dir = validation_api.prepare_session(session_id)
        # Ensure clean state before starting
        validation_api.clean_dir(Path(output_dir))

        status_file = validation_api.get_status_file_path(session_id)

        validation_api.run_validation_background(
            input_dir,
            output_dir,
            validation_gate,
            validation_api.RULE_SET_DIR,
            status_file,
        )

        return (
            False,  # Enable interval
            True,  # Disable button
            0,  # Reset progress
            "Starting...",
            {"display": "flex", "height": "20px"},  # Show progress bar
        )

    @app.callback(
        Output("validation-progress", "value"),
        Output("validation-progress", "label", allow_duplicate=True),
        Output("progress-interval", "disabled"),
        Output("btn-validate", "disabled"),
        Output("validation-progress", "style", allow_duplicate=True),
        Output("download-validation-result", "children"),
        Output("validation-result", "children"),
        Input("progress-interval", "n_intervals"),
        prevent_initial_call=True,
    )
    def update_progress(n: int) -> Tuple[Any, ...]:
        """
        Polls the status file and updates the progress bar.
        """
        session_id = get_or_create_session_id()
        status_file = validation_api.get_status_file_path(session_id)

        if not os.path.exists(status_file):
            return no_update

        try:
            with open(status_file, "r") as f:
                data = json.load(f)

            progress = data.get("progress", 0)
            message = data.get("message", "")
            state = data.get("state", "running")
            result = data.get("result", [])

            if state in ["completed", "error"]:
                log_display = (
                    [html.Div(line) for line in result]
                    if isinstance(result, list)
                    else [html.Div(str(result))]
                )
                download_link = html.A(
                    "Download validation results",
                    href=f"/download_results/{session_id}",
                    target="_blank",
                )
                return (
                    100,
                    "Done" if state == "completed" else "Error",
                    True,  # Disable interval
                    False,  # Enable button
                    {"display": "none"},  # Hide progress
                    download_link,
                    log_display,
                )

            return (
                progress,
                message,
                False,  # Keep interval
                True,  # Keep button disabled
                {"display": "flex", "height": "20px"},
                no_update,
                no_update,
            )

        except (json.JSONDecodeError, OSError):
            return no_update

    @app.callback(
        Output("rsl-upload-status", "children"),
        Output("rsl-version", "children"),
        Output("btn-validate", "disabled", allow_duplicate=True),
        Output("validation-gate-dropdown", "disabled"),
        Output("system-status-alert", "children"),
        Output("system-status-alert", "color"),
        Output("rsl-accordion", "active_item"),
        Input("upload-rsl", "contents"),
        Input("page-state", "pathname"),
        State("upload-rsl", "filename"),
        prevent_initial_call="initial_duplicate",
    )
    def update_rsl_and_status(
        contents: Optional[str], pathname: str, filename: Optional[str]
    ) -> Tuple[Any, ...]:
        """
        Handles RSL file uploads and updates the system status.
        """
        triggered_id = ctx.triggered_id

        # Handle RSL Upload
        upload_msg = None
        if triggered_id == "upload-rsl" and contents is not None:
            if filename and filename.endswith(".zip"):
                try:
                    validation_api.update_rsl_from_base64(contents)
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
