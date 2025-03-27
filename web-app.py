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

#external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

server = Flask(__name__)
server.secret_key = "your-secret-key"  # Required for session
app = dash.Dash(__name__, server=server)

#app = dash.Dash(__name__)#, external_stylesheets=external_stylesheets)

app.layout = html.Div([
    dcc.Location(id='page-state', refresh=False),
    html.Button('Validate', id='btn-validate'),
    html.Button('Delete All', id='btn-delete-all'),
    html.Button('Delete All but BDS', id='btn-delete-all-keep-bds'),
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        # Allow multiple files to be uploaded
        multiple=True
    ),
    html.Div(id='uploaded-files'),
    html.Div(id='folder-content'),
    #dcc.Interval(id="interval", interval=3000),
    html.Div(id='delete-all'),
    html.Div(id='validation-result')
])


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


# Run validation
# Delte IGM-s
# Delte BDS
# Delte all files
# Delete single files
# Explore files/errors

## Functions
# List all files
# Delete files given in a list
# List RSL and Validator version






def get_ruleset_version():
    pass


def run_valdation():
    pass

def download_validation_results():
    pass

if __name__ == '__main__':
    app.run(debug=True)