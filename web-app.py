import dash
from dash.dependencies import Input, Output, State
from dash import dcc, html, dash_table
from flask import Flask, send_file, session

import uuid

import validation_api

#import pandas as pd
import os
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
    dcc.Interval(id="interval", interval=1000),
    html.Div(id='delete-all'),
    html.Div(id='validation-result')
])


@app.callback(Output("uploaded-files", "children"),
              Input('upload-data', 'contents'),
              State('upload-data', 'filename')
              )
def upload_files(list_of_contents, list_of_names):
    _, model_input, _ = validation_api.create_validation_context(get_or_create_session_id())

    if list_of_contents is not None:
        for file_name, content in zip(list_of_names, list_of_contents):
            file_path = os.path.join(model_input, file_name)
            with open(file_path, "w") as file_object:
                file_object.write(content)


@app.callback(Output('delete-all', "children"),
              Input('btn-delete-all', "n_clicks"),
              )
def delete_all(n_clicks):
    _, model_input, _ = validation_api.create_validation_context(get_or_create_session_id())

    if n_clicks:
        [item.unlink() for item in Path(model_input).glob("*") if item.is_dir() is False]


@app.callback(Output('folder-content', 'children'),
              Input('interval', "n_intervals"))
def list_files(_):
    _, model_input, _ = validation_api.create_validation_context(get_or_create_session_id())
    return [html.Li(item.name) for item in Path(model_input).glob("*") if item.is_dir() is False]

@server.route("/validate/<validation_instance>")
def download_file(validation_instance):
    _, input_dir, output_dir = validation_api.create_validation_context(validation_instance)
    result = validation_api.run_validation(input_dir, output_dir)
    if result:
        return send_file(result, mimetype='application/zip', as_attachment=True, download_name="output.zip")
    return "Validation failed", 500


@app.callback(Output('validation-result', 'children'),
              Input('btn-validate', "n_clicks"))
def validate(n_clicks):
    if n_clicks:
        session_id = get_or_create_session_id()
        return html.A("Download validation results", href=f"/validate/{session_id}", target="_blank")






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





def delete_files(list_of_paths):
    pass

def get_ruleset_version():
    pass

def get_validator_version():
    pass

def run_valdation():
    pass

def download_validation_results():
    pass

if __name__ == '__main__':
    app.run(debug=True)