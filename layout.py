from dash import dcc, html
import dash_bootstrap_components as dbc
import base64
import validation_api
from config import Config


def create_layout(app_version: str, svg_logo: str) -> html.Div:
    """
    Creates the main Dash application layout.

    Args:
        app_version: The current application version string.
        svg_logo: The raw SVG content string for the logo.

    Returns:
        The Dash HTML layout component.
    """
    return html.Div(
        className="app-container",
        children=[
            # Header
            html.Div(
                className="app-header",
                children=[
                    # Left side: Logo and App Name
                    html.Div(
                        className="header-left",
                        children=[
                            html.Img(
                                src=f"data:image/svg+xml;base64,{base64.b64encode(svg_logo.encode('utf-8')).decode('utf-8')}",
                                className="app-logo",
                            ),
                            html.H1("Validator UI", className="app-title"),
                        ],
                    ),
                    # Right side: Swagger Button and RSL Version
                    html.Div(
                        className="header-right",
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
                                className="rsl-version",
                            ),
                        ],
                    ),
                ],
            ),
            # Main content
            html.Div(
                className="main-content",
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
                                        className="upload-box",
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
                                    {"label": "BDS", "value": "bds"},
                                ],
                                value="full",
                                clearable=False,
                                className="validation-gate-dropdown",
                                disabled=True,
                            ),
                        ],
                        className="validation-gate-container",
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
                    dcc.Interval(
                        id="progress-interval",
                        interval=Config.PROGRESS_POLL_INTERVAL_MS,
                        n_intervals=0,
                        disabled=True,
                    ),
                    dbc.Progress(
                        id="validation-progress",
                        value=0,
                        striped=True,
                        animated=True,
                        className="progress-bar-container",
                        # style is handled dynamically via callback for display
                        style={"display": "none"},
                    ),
                    dcc.Loading(
                        id="loading-upload",
                        type="default",
                        children=[
                            dcc.Upload(
                                id="upload-data",
                                children=html.Div(
                                    [
                                        "Drag and Drop or ",
                                        html.A("Select Files"),
                                        " for validation.",
                                    ]
                                ),
                                className="upload-box",
                                multiple=True,
                            ),
                        ],
                    ),
                    html.Div(id="uploaded-files"),
                    html.Div(id="folder-content"),
                    html.Div(id="download-validation-result"),
                    html.Div(
                        id="validation-result",
                        children=None,
                        className="validation-results",
                    ),
                ],
            ),
        ],
    )
