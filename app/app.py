import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import flask
import plotly.express as px
import dash.dependencies
import pandas as pd
import random
import requests

server = flask.Flask(__name__)
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.config.suppress_callback_exceptions = True

app.title = 'Tasa de positividad por COVID-19 en Chile'

green_rect_props = {
    "y0":0,
    "y1":0.05,
    "line_width":0,
    "fillcolor":"green",
    "opacity":0.2,
    "annotation_text":"Tasa de positividad recomendada",
    "annotation_position":"bottom left",
    "annotation_font":{
        "color":"darkgreen"
    }
}

alphabet = "abcdefghijklmnopqrstuvwxyz"
def normalize(word):
    word = word.lower()
    word = word.replace("á","a")
    word = word.replace("é","e")
    word = word.replace("è","e")
    word = word.replace("í","i")
    word = word.replace("î","i")
    word = word.replace("ó","o")
    word = word.replace("ú","u")
    word = word.replace("ü","u")
    word = word.replace("ḿ","m")
    word = word.replace("ń","m")
    word = word.replace("ñ","n")
    result = [l for l in word if l in alphabet]
    return "".join(result)

def get_country_data():
    country_data = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto49/Positividad_Diaria_Media_std.csv",parse_dates=["Fecha"])
    # country_data["Total"] = random.random()
    return country_data[country_data.Serie.isin(["positividad"])]

def get_communal_data(selected_communes = None):
    positivity_by_commune = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto65/PositividadPorComuna_std.csv",parse_dates=["Fecha"])
    positivity_by_commune["Positividad"] = positivity_by_commune["Positividad"]/100
    # positivity_by_commune["Positividad"] = random.random()
    if selected_communes == None:
        return positivity_by_commune
    else:
        return positivity_by_commune.loc[positivity_by_commune.Comuna.isin(selected_communes)]

def get_rm_choropleth_data():
    positivity_by_commune = get_communal_data()
    positivity_by_commune["Comuna norm"] = positivity_by_commune["Comuna"].apply(normalize)
    max_date_idx = positivity_by_commune.loc[positivity_by_commune["Codigo region"] == 13][["Comuna norm","Fecha"]].groupby(by=["Comuna norm"])["Fecha"].idxmax()
    return positivity_by_commune.loc[max_date_idx]

def get_rm_geo_data():
    communes_g = requests.get("https://raw.githubusercontent.com/jlhonora/geo/master/region_metropolitana_de_santiago/all.geojson").json()
    for i,feature in enumerate(communes_g["features"]):
        communes_g["features"][i]["properties"]["NOM_COM_NORM"] = normalize(feature["properties"]["NOM_COM"])
    return communes_g

def choropleth_fig():
    fig = px.choropleth(
        get_rm_choropleth_data(), 
        geojson=get_rm_geo_data(), 
        color_continuous_scale="Oranges",
        locations="Comuna norm", 
        color='Positividad',
        featureidkey="properties.NOM_COM_NORM",
        hover_data={"Comuna":True,"Positividad":":.1%","Comuna norm":False}
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(coloraxis_colorbar_tickformat='.1%')
    return fig

communes = get_communal_data().Comuna.value_counts().index.tolist()
commune_options = [{"label":commune,"value":commune} for commune in communes]

figure_layout = {
    "transition_duration":500,
    "yaxis":{
        "tickformat":".1%"
        }
}

def country_positivity_fig():
    fig = px.line(
        data_frame = get_country_data(),
        x = "Fecha",
        y = "Total",
        labels=dict(Total="Tasa de positividad")
    )
    fig.add_hrect(**green_rect_props)
    fig.update_layout(**figure_layout)
    return fig

def serve_layout():
    return html.Div(className = "container-md" ,children=[
        html.H1(children='Positividad por Coronavirus en Chile'),

        html.Div(children=f'''
            La tasa de positividad es  el porcentaje de personas que dan positivo para la infección de entre todas a las que se les ha hecho prueba PCR durante un tiempo determinado. La Organización Mundial de la Salud (OMS) recomienda que ese porcentaje se quede por debajo del 5 %.
        '''),
        html.H2(children="Tasa de positividad por día en el territorio nacional"),
        dcc.Graph(
            id='general-positivity',
            figure=country_positivity_fig()
        ),
        html.H2(children="Tasa de positividad semanal por comuna"),
        html.Div([
            dcc.Dropdown(
                options=commune_options,
                value=[],
                placeholder="Seleccione las comunas a visualizar",
                multi=True,
                id="commune-dropdown"
            ),
            dcc.Graph(id='graph-with-dropdown'),
        ]),
        html.H2(children="Última tasa de positividad en la Región Metropolitana"),
        dcc.Graph(
            id='choropleth',
            figure=choropleth_fig()
        ),
    ])

app.layout = serve_layout

@app.callback(
    dash.dependencies.Output('graph-with-dropdown', 'figure'),
    dash.dependencies.Input('commune-dropdown', 'value'))
def update_figure(selected_communes):
    selected_communes = selected_communes if selected_communes else ["Santiago"]
    fig = px.line(
        data_frame = get_communal_data(selected_communes),
        x = "Fecha",
        y = "Positividad",
        color = "Comuna",
        labels=dict(Positividad="Tasa de positividad")
    )
    fig.add_hrect(**green_rect_props)
    fig.update_layout(**figure_layout)

    return fig

if __name__ == "__main__":
    import os
    debug = False if os.environ["DASH_DEBUG_MODE"] == "False" else True
    app.run_server(host="0.0.0.0", port=8050, debug=debug)
