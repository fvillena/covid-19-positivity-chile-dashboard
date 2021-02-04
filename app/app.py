import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import flask
import plotly.express as px
import plotly.subplots
import dash.dependencies
import pandas as pd
import numpy as np
import geopandas as gpd
import json
import random
import requests
import time
import pathlib
import logging
logger = logging.getLogger(__name__)
app_folder = pathlib.Path(__file__).parent.absolute()

country_data = None
country_vaccination_data = None
positivity_by_commune = None
cases_by_region = None
tests_by_region = None
country_data_last_update = 0
country_vaccination_data_update = 0
positivity_by_commune_last_update = 0
cases_by_region_last_update = 0
tests_by_region_last_update = 0

period = 3600
POPULATION = 18.73*10**6

green_rect_props = {
    "y0":0,
    "y1":0.05,
    "line_width":0,
    "fillcolor":"green",
    "opacity":0.2,
    "annotation_text":"Positividad recomendada",
    "annotation_position":"bottom left",
    "annotation_font":{
        "color":"darkgreen"
    }
}

figure_layout = {
    "transition_duration":500,
    "yaxis":{
        "tickformat":".1%",
        "fixedrange":True,
        "automargin":True
        },
    "xaxis":{
        "fixedrange":True,
        "automargin":True,
        },
    "legend": {
        "orientation": 'h',
        "yanchor":"bottom",
        "y":1.03,
        "xanchor":"right",
        "x":1
    },
    "margin":{
        "r":5
    }
    
}

meta_tags = [
    # A description of the app, used by e.g.
    # search engines when displaying search results.
    {
        'name': 'description',
        'content': 'Tasa de positividad y vacunación por coronavirus en chile por región y fecha. La positividad debiese mantenerse bajo el 5 % y la vacunación al 80 %.'
    },
    # A tag that tells Internet Explorer (IE)
    # to use the latest renderer version available
    # to that browser (e.g. Edge)
    {
        'http-equiv': 'X-UA-Compatible',
        'content': 'IE=edge'
    },
    # A tag that tells the browser not to scale
    # desktop widths to fit mobile screens.
    # Sets the width of the viewport (browser)
    # to the width of the device, and the zoom level
    # (initial scale) to 1.
    #
    # Necessary for "true" mobile support.
    {
      'name': 'viewport',
      'content': 'width=device-width, initial-scale=1.0'
    }
]

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
    global country_data
    global country_data_last_update
    if time.time() - country_data_last_update > period:
        logger.info("downloading country_data")
        country_data = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto49/Positividad_Diaria_Media_std.csv",parse_dates=["Fecha"])
        country_data_last_update = time.time()
    # country_data["Total"] = random.random()
    return country_data[country_data.Serie.isin(["positividad"])]

def get_country_vaccination_data():
    global country_vaccination_data
    global country_vaccination_data_update
    if time.time() - country_vaccination_data_update > period:
        logger.info("downloading country_vaccination_data")
        vaccination_country_data = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto76/vacunacion_std.csv")
        vaccination_country_data = vaccination_country_data.loc[(vaccination_country_data.Region == "Total") & (vaccination_country_data.Dosis == "Segunda")]
        vaccination_country_data.loc[:,"Total"] = vaccination_country_data.Cantidad.cumsum()
        vaccination_country_data.replace(0, np.nan, inplace=True)
        vaccination_country_data.loc[:,"Proporción de vacunados"] = vaccination_country_data["Total"] / POPULATION
    return vaccination_country_data

def get_communal_data(selected_communes = None):
    global positivity_by_commune
    global positivity_by_commune_last_update
    if time.time() - positivity_by_commune_last_update > period:
        logger.info("downloading communal_data")
        positivity_by_commune = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto65/PositividadPorComuna_std.csv",parse_dates=["Fecha"])
        positivity_by_commune_last_update = time.time()
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

def get_by_region_data():
    global cases_by_region
    global tests_by_region
    global cases_by_region_last_update
    global tests_by_region_last_update
    if time.time() - cases_by_region_last_update > period:
        logger.info("downloading cases_by_region")
        cases_by_region = pd.read_csv("https://raw.githubusercontent.com/MinCiencia/Datos-COVID19/master/output/producto3/TotalesPorRegion_std.csv")
        cases_by_region = cases_by_region.loc[cases_by_region.Categoria == "Casos nuevos totales"]
    if time.time() - tests_by_region_last_update > period:
        logger.info("downloading tests_by_region")
        tests_by_region = pd.read_csv("https://raw.githubusercontent.com/MinCiencia/Datos-COVID19/master/output/producto7/PCR_std.csv")
    positivity_by_region = cases_by_region.merge(
        tests_by_region.rename(columns={"fecha":"Fecha","numero":"Pruebas"})[["Region","Fecha","Pruebas","Codigo region"]],
        how="inner",
        validate="one_to_one"
    )
    positivity_by_region["Positividad"] = positivity_by_region.Total / positivity_by_region.Pruebas
    positivity_by_region.dropna(inplace=True)
    positivity_by_region["Fecha"] = pd.to_datetime(positivity_by_region["Fecha"])
    return positivity_by_region

def get_country_choropeth_data():
    positivity_by_region = get_by_region_data()
    max_date_idx = positivity_by_region.groupby(by=["Region"])["Fecha"].idxmax()
    return positivity_by_region.loc[max_date_idx]

def choropleth_fig():
    fig = px.choropleth_mapbox(
        get_rm_choropleth_data(), 
        geojson=communes_g, 
        color_continuous_scale="PiYG_r",
        color_continuous_midpoint=0.05,
        locations="Comuna norm", 
        color='Positividad',
        featureidkey="properties.NOM_COM_NORM",
        hover_data={"Comuna":True,"Positividad":":.1%","Comuna norm":False},
        mapbox_style="carto-positron",
        zoom=7.5,
        center = {"lat": -33.5826900, "lon": -70.6472400},
        opacity=0.5
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(coloraxis_showscale=False,margin={"r":5,"t":0,"l":5,"b":0})
    return fig

def choropleth_country_fig():
    fig = px.choropleth_mapbox(
        get_country_choropeth_data(), 
        geojson=chile_g_geojson, 
        color_continuous_scale="PiYG_r",
        color_continuous_midpoint=0.05,
        locations="Codigo region", 
        color='Positividad',
        featureidkey="properties.COD_REGI",
        hover_data={"Region":True,"Positividad":":.1%","Codigo region":False},
        height=800,
        mapbox_style="carto-positron",
        zoom=3.4,
        center = {"lat": -39, "lon": -70.6653},
        opacity=0.5
    )
    # fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(coloraxis_showscale=False,margin={"r":5,"t":0,"l":5,"b":0})
    return fig

def country_positivity_fig():
    fig = plotly.subplots.make_subplots(specs=[[{"secondary_y": True}]])
    f1 = px.line(
        data_frame = get_country_data(),
        x = "Fecha",
        y = "Total",
        labels=dict(Total="Tasa de positividad",
        )
    )
    f2 = px.line(
        data_frame = get_country_vaccination_data(),
        x = "Fecha",
        y = "Proporción de vacunados",
    )
    f1['data'][0]['showlegend']=True
    f1['data'][0]['name']='Positividad'
    f2['data'][0]['showlegend']=True
    f2['data'][0]['name']='Vacunación'
    f2.update_traces(yaxis="y2")
    fig.add_traces(f1.data + f2.data)
    fig.layout.xaxis.title="Fecha"
    fig.layout.yaxis.title="Tasa de positividad"
    fig.layout.yaxis2.title="Proporción de vacunados"
    fig.for_each_trace(lambda t: t.update(line=dict(color=t.marker.color)))
    fig.add_hrect(**green_rect_props)
    fig.update_layout(**figure_layout)
    yaxis2_layout = {
        "yaxis2":{
            "tickformat":".1%",
            "fixedrange":True,
            "automargin":True,
            "range":[0,1]
            },
    }
    fig.update_layout(**yaxis2_layout)
    fig.update_layout(showlegend=True)
    xaxes_layout = {
        "rangeslider":{
            "visible":True
            },
    }
    fig.update_xaxes(**xaxes_layout)
    return fig

def serve_layout():
    return html.Div(className = "container-md" ,children=[
        html.H1(children='Positividad y Vacunación por Coronavirus en Chile'),

        html.Div(children=f'''
            La tasa de positividad es  el porcentaje de personas que dan positivo para la infección de entre todas a las que se les ha hecho prueba PCR durante un tiempo determinado. La Organización Mundial de la Salud (OMS) recomienda que ese porcentaje se quede por debajo del 5 %. La vacunación en Chile debiese llegar al menos a un 80 %.
        '''),
        html.H2(children="Tasa de positividad y vacunación por día en el territorio nacional"),
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
        html.H2(children="Última tasa de positividad en el territorio nacional"),
        dcc.Graph(
            id='choropleth-country',
            figure=choropleth_country_fig()
        ),
        html.Div(children=[html.Hr()] + ["Hecho con 🧠 y 🐍 por "] + [html.A("Fabián Villena", href="https://fabianvillena.cl/")]),
    ])

with open(app_folder / "data/rm.geojson") as j:
        communes_g = json.load(j)
for i,feature in enumerate(communes_g["features"]):
    communes_g["features"][i]["properties"]["NOM_COM_NORM"] = normalize(feature["properties"]["NOM_COM"])

chile_g = gpd.read_file(app_folder / "data/cl.geojson")
chile_g = chile_g.dropna().sort_values("COD_REGI")
chile_g_geojson = json.loads(chile_g.to_json())

communes = get_communal_data().Comuna.value_counts().index.tolist()
commune_options = [{"label":commune,"value":commune} for commune in communes]

server = flask.Flask(__name__)
app = dash.Dash(__name__, server=server, meta_tags=meta_tags, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.config.suppress_callback_exceptions = True
app.title = 'Tasa de positividad por COVID-19 en Chile'


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
        labels=dict(Positividad="Tasa de positividad"),

    )
    fig.add_hrect(**green_rect_props)
    fig.update_layout(**figure_layout)

    return fig

if __name__ == "__main__":
    import os
    debug = False if os.environ.get("DASH_DEBUG_MODE", True) == "False" else True
    port = int(os.environ.get("PORT", 8050))
    app.run_server(host="0.0.0.0", port=port, debug=debug)
