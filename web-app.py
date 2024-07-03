import subprocess

import dash
from dash.dependencies import Input, Output, State
from dash import dcc, html, dash_table

import pandas as pd
from pathlib import Path

model_input = Path(r"C:\Users\kristjan.vilgo\Documents\GitHub\ENTOSE-RULE-SET\dockerized-qocdc\input")

#external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__)#, external_stylesheets=external_stylesheets)

app.layout = html.Div([
    html.Button('Validate', id='btn-validate'),
    html.Button('Delete All', id='btn-delete-all'),
    html.Button('Delere All but BDS', id='btn-delete-all-keep-bds'),
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

    if list_of_contents is not None:
        for file_name, content in zip(list_of_names, list_of_contents):
            file_path = model_input / file_name
            with file_path.open("w") as file_object:
                file_object.write(content)


@app.callback(Output('delete-all', "children"),
              Input('btn-delete-all', "n_clicks"),
              )
def delete_all(n_clicks):
    if n_clicks:
        [item.unlink() for item in Path(model_input).glob("*") if item.is_dir() is False]


@app.callback(Output('folder-content', 'children'),
              Input('interval', "n_intervals"))
def list_files(_):
    return [html.Li(item.name) for item in Path(model_input).glob("*") if item.is_dir() is False]

@app.callback(Output('validation-result', 'children'),
              Input('btn-validate', "n_clicks"))
def validate(n_clicks):
    if n_clicks:
        return("\n".join(subprocess.run("validate.bat", capture_output=True, text=True)[1]))






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
    app.run_server(debug=True)