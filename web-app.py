import dash
from dash.dependencies import Input, Output, State
from dash import dcc, html, dash_table, no_update, ctx
from flask import Flask, send_file, session, request, jsonify

import base64
import uuid
import validation_api

#import pandas as pd

from pathlib import Path

def get_or_create_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

server = Flask(__name__)
server.secret_key = "your-secret-key"  # Required for session
app = dash.Dash(__name__, server=server, external_stylesheets=external_stylesheets, title="Validator")

#app = dash.Dash(__name__)#, external_stylesheets=external_stylesheets)

# Load SVG logo (with fallback if not available)
try:
    with open("assets/logo.svg", "r") as f:
        svg_logo = f.read()
except FileNotFoundError:
    # Fallback SVG if logo.svg is not available
    svg_logo = '''
    <svg width="40" height="40" xmlns="http://www.w3.org/2000/svg">
        <rect width="40" height="40" fill="#ffffff"/>
        <text x="10" y="25" fill="#000000">Logo</text>
    </svg>
    '''

# Override the default HTML to set body margin to 0
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            html, body {
                margin: 0;
                padding: 0;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# App layout with header and fixes
app.layout = html.Div(
    style={
        'margin': '0',  # Remove default margin to eliminate white border
        'padding': '0',
        'minHeight': '100vh',  # Ensure full height
        'boxSizing': 'border-box'
    },
    children=[
        # Header with black background
        html.Div(
            style={
                'backgroundColor': '#000000',  # Black background
                'padding': '10px',
                'display': 'flex',
                'justifyContent': 'space-between',
                'alignItems': 'center',
                'color': '#ffffff',  # White text
                'margin': '0',  # Ensure no margin
                'width': '100%',  # Full width
                'boxSizing': 'border-box'
            },
            children=[
                # Left side: Logo and App Name
                html.Div(
                    style={'display': 'flex', 'alignItems': 'center'},
                    children=[
                        html.Img(
                            src=f"data:image/svg+xml;base64,{base64.b64encode(svg_logo.encode('utf-8')).decode('utf-8')}",
                            style={'height': '45px', 'marginRight': '10px'}
                        ),
                        html.H1("Validator UI", style={'fontSize': '24px', 'margin': '0'})
                    ]
                ),
                # Right side: RSL Version
                html.Div(
                    f"App: 0.0.1        RSL: {validation_api.get_ruleset_version()}",
                    style={'fontSize': '18px'}
                )
            ]
        ),
        # Main content with constrained width
        html.Div(
            style={
                'maxWidth': '1200px',  # Constrain content width
                'margin': '0 auto',  # Center content
                'padding': '20px',
                'boxSizing': 'border-box'
            },
            children=[
                dcc.Location(id='page-state', refresh=False),
                html.Button('Validate', id='btn-validate'),
                html.Button('Delete All', id='btn-delete-all'),
                html.Button('Delete All but BDS', id='btn-delete-all-keep-bds'),
                dcc.Upload(
                    id='upload-data',
                    children=html.Div([
                        'Drag and Drop or ',
                        html.A('Select Files'),
                        ' for validation.'
                    ]),
                    style={
                        'width': '100%',  # Full width within parent
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '10px 0',  # Adjust margin to avoid overflow
                        'boxSizing': 'border-box'  # Include border in width
                    },
                    multiple=True
                ),
                html.Div(id='uploaded-files'),
                html.Div(id='folder-content'),
                html.Div(id='delete-all'),
                html.Div(id='validation-result')
            ]
        )
    ]
)


from dash import ctx  # Dash >=2.0 for `ctx.triggered_id`

def get_file_list_ui(model_input):
    return [html.Li(item.name) for item in Path(model_input).glob("*") if not item.is_dir()]


@app.callback(
    Output('folder-content', 'children'),
    Input('page-state', 'pathname'),  # triggers on load/refresh
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    Input('btn-delete-all', 'n_clicks'),
    Input('btn-delete-all-keep-bds', 'n_clicks')
)
def manage_files(pathname, upload_contents, upload_names, delete_clicks, keep_bds_clicks):
    _, model_input, model_output = validation_api.create_validation_context(get_or_create_session_id())

    triggered_id = ctx.triggered_id
    if triggered_id == 'upload-data' and upload_contents:

        for name, content in zip(upload_names, upload_contents):
            content_string = content.split(',')[1]
            decoded = base64.b64decode(content_string)
            with open(Path(model_input) / name, "wb") as f:
                f.write(decoded)

        return get_file_list_ui(model_input)

    elif triggered_id == 'btn-delete-all' and delete_clicks:

        validation_api.clean_dir(Path(model_input))
        validation_api.clean_dir(Path(model_output))

        return get_file_list_ui(model_input)

    elif triggered_id == 'btn-delete-all-keep-bds' and keep_bds_clicks:

        validation_api.clean_dir(Path(model_output))

        for item in Path(model_input).glob("*"):
            if item.is_file() and not "BD_" in item.name:
                item.unlink()

        return get_file_list_ui(model_input)

    if triggered_id == 'page-state':
        return get_file_list_ui(model_input)

    return no_update

@app.callback(Output('validation-result', 'children'),
              Input('btn-validate', "n_clicks"))
def validate(n_clicks):
    if n_clicks:
        session_id = get_or_create_session_id()
        _, _, model_output = validation_api.create_validation_context(get_or_create_session_id())
        validation_api.clean_dir(Path(model_output))
        return html.A("Download validation results", href=f"/validate/{session_id}", target="_blank")

@server.route("/validate/<validation_instance>")
def download_file(validation_instance):
    _, input_dir, output_dir = validation_api.create_validation_context(validation_instance)
    result = validation_api.run_validation(input_dir, output_dir)
    if result:
        return send_file(result, mimetype='application/zip', as_attachment=True, download_name="output.zip")
    return "Validation failed", 500

@server.route('/upload', methods=['POST'])
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
            filename = file["name"]
            content = base64.b64decode(file["content"])
            file_path = Path(input_dir) / filename
            with open(file_path, "wb") as f:
                f.write(content)
        except Exception as e:
            return jsonify({"error": f"Failed to process file '{file.get('name', 'unknown')}': {str(e)}"}), 500

    return jsonify({"validation_id": validation_id}), 200



## Functions
# List all files
# Delete all files
# Delete all files except BDS
# Show RSL version
# Upload/Update RSL
# Show logs? probably sent to ELK





def get_ruleset_version():
    pass


def run_valdation():
    pass

def download_validation_results():
    pass

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8050, debug=False)