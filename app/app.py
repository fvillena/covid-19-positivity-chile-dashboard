import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import flask
import plotly.express as px
import plotly.subplots
import plotly.graph_objects as go
import dash.dependencies
import pandas as pd
import scipy.stats
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
vaccination_country_data = None
positivity_by_commune = None
cases_by_region = None
tests_by_region = None
step_data = None
step_data_last_update = 0
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

def get_step_data():
    global step_data
    global step_data_last_update
    if time.time() - step_data_last_update > period:
        logger.info("downloading step_data")
        step_data = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto74/paso_a_paso_std.csv")
        step_data.rename(columns={"comuna_residencia":"Comuna"},inplace=True)
        step_data = step_data[(step_data.zona == "Total") & (step_data.codigo_region == 13)]
        step_data = step_data.pivot(index="Comuna", columns="Fecha", values="Paso")
        step_data_last_update = time.time()
    return step_data

def get_trend(y):
    x = range(len(y))
    result = scipy.stats.linregress(x, y)
    return result.slope

def get_country_data(return_moving_average = False):
    global country_data
    global country_data_last_update
    if time.time() - country_data_last_update > period:
        logger.info("downloading country_data")
        country_data = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto49/Positividad_Diaria_Media_std.csv",parse_dates=["Fecha"])
        mapper = {
            "positividad pcr":"positividad",
            "mediamovil_positividad_pcr":"mediamovil_positividad"
        }
        country_data["Serie"] = country_data.Serie.apply(lambda x: mapper[x] if x in mapper else x)
        country_data_last_update = time.time()
    if return_moving_average:
        result = country_data[country_data.Serie.isin(["mediamovil_positividad"])]
    else:
        result = country_data[country_data.Serie.isin(["positividad"])]
    return result

def get_country_vaccination_data():
    global vaccination_country_data
    global country_vaccination_data_update
    if time.time() - country_vaccination_data_update > period:
        logger.info("downloading country_vaccination_data")
        vaccination_country_data = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto76/vacunacion_std.csv")
        vaccination_country_data = vaccination_country_data.loc[vaccination_country_data.Region == "Total"]
        vaccination_country_data.loc[:,"Total"] = vaccination_country_data.Cantidad
        vaccination_country_data.replace(0, np.nan, inplace=True)
        vaccination_country_data.loc[:,"Proporción de vacunados"] = vaccination_country_data["Total"] / POPULATION
        vaccination_country_data.loc[:,"Esquema"] = np.where(vaccination_country_data.Dosis.isin(["Segunda","Unica"]),"Completo","Incompleto")
        vaccination_country_data = vaccination_country_data.groupby(by=["Region","Fecha","Esquema"])[["Cantidad","Total","Proporción de vacunados"]].sum().reset_index()
        country_vaccination_data_update = time.time()
    return vaccination_country_data

def get_communal_data(selected_communes = None):
    global positivity_by_commune
    global positivity_by_commune_last_update
    if time.time() - positivity_by_commune_last_update > period:
        logger.info("downloading communal_data")
        positivity_by_commune = pd.read_csv("https://github.com/MinCiencia/Datos-COVID19/raw/master/output/producto65/PositividadPorComuna_std.csv",parse_dates=["Fecha"], na_values=["-"])
        positivity_by_commune["Positividad"] = positivity_by_commune["Positividad"]/100
        positivity_by_commune_last_update = time.time()
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
        cases_by_region_last_update = time.time()
    if time.time() - tests_by_region_last_update > period:
        logger.info("downloading tests_by_region")
        tests_by_region = pd.read_csv("https://raw.githubusercontent.com/MinCiencia/Datos-COVID19/master/output/producto7/PCR_std.csv")
        tests_by_region_last_update = time.time()
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

def step_fig():
    fig = px.imshow(
        get_step_data(),
        color_continuous_scale=["#dc3545","#ffc107","yellow","#28a745"],
        zmin=1,
        zmax=4,
        height=1000
    )
    fig.layout.coloraxis.showscale=False
    fig.update_traces(hovertemplate='Fecha: %{x} <br>Comuna: %{y} <extra></extra>')
    return fig

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

def country_positivity_fig_new():
    fig = px.line(
        data_frame = get_country_data(),
        x = "Fecha",
        y = "Total",
        labels=dict(Total="Tasa de positividad"),

    )
    fig.add_hrect(**green_rect_props)
    fig.update_layout(**figure_layout)
    fig.layout.yaxis.title="Tasa de positividad"
    xaxes_layout = {
        "rangeslider":{
            "visible":True
            },
    }
    fig.update_xaxes(**xaxes_layout)
    return fig

def country_vaccination_fig():
    fig = px.line(
        data_frame = get_country_vaccination_data(),
        x = "Fecha",
        y = "Proporción de vacunados",
        color = "Esquema"

    )
    fig.update_layout(**figure_layout)
    xaxes_layout = {
        "rangeslider":{
            "visible":True
            },
    }
    fig.add_hrect(**{
    "y0":0.8,
    "y1":1,
    "line_width":0,
    "fillcolor":"green",
    "opacity":0.2,
    "annotation_text":"Vacunación recomendada",
    "annotation_position":"bottom left",
    "annotation_font":{
        "color":"darkgreen"
    }
})
    fig.update_xaxes(**xaxes_layout)
    fig.layout.yaxis.range=[0,1]
    return fig

def indicators_fig():
    last_positivity = get_country_data().sort_values("Fecha",ascending=False).reset_index(drop=True).loc[0]
    last_vaccination = get_country_vaccination_data()[get_country_vaccination_data()["Esquema"] == "Completo"].sort_values("Fecha",ascending=False).reset_index(drop=True).loc[0]
    last_last_vaccination = get_country_vaccination_data()[get_country_vaccination_data()["Esquema"] == "Completo"].sort_values("Fecha",ascending=False).reset_index(drop=True).loc[1]
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode = "number",
        title = {
            "text":f"Positividad<br><span style='font-size:0.8em;color:gray'>{last_positivity['Fecha'].strftime('%d/%m/%Y')}</span>"
        },
        number = {'valueformat':".1%"},
        value = last_positivity["Total"],
        domain = {'row': 0, 'column': 0}))
    fig.add_trace(go.Indicator(
        mode = "number",
        title = {
            "text":f"Vacunación<br><span style='font-size:0.8em;color:gray'>{pd.to_datetime(last_vaccination['Fecha']).strftime('%d/%m/%Y')}</span>"
        },
        number = {'valueformat':".1%"},
        value = last_vaccination["Proporción de vacunados"],
        domain = {'row': 0, 'column': 1}))
    fig.add_trace(go.Indicator(
        title = "<span style='font-size:0.8em'>Cambio diario</span>",
        mode = "delta",
        value = get_trend(get_country_data(return_moving_average=True).iloc[-7:,:]["Total"]),
        delta = go.indicator.Delta(
            reference = 0, 
            valueformat = ".2%",
            decreasing = go.indicator.delta.Decreasing(
                color="green"
            ),
            increasing = go.indicator.delta.Increasing(
                color="red"
            ),
            ),
        domain = {'row': 1, 'column': 0}))
    fig.add_trace(go.Indicator(
        title = "<span style='font-size:0.8em'>Cambio diario</span>",
        mode = "delta",
        value = last_vaccination["Proporción de vacunados"],
        delta = go.indicator.Delta(
            reference = last_last_vaccination["Proporción de vacunados"], 
            valueformat = ".2%"
            ),
        domain = {'row': 1, 'column': 1}))
    fig.update_layout(
        grid = {'rows': 2, 'columns': 2, 'pattern': "independent"})
    return fig

def serve_layout():
    return dbc.Container(className = "md" ,children=[
        html.H1(children='Positividad y Vacunación por Coronavirus en Chile'),

        html.Div(children=f'''
            La tasa de positividad es  el porcentaje de personas que dan positivo para la infección de entre todas a las que se les ha hecho prueba PCR durante un tiempo determinado. La Organización Mundial de la Salud (OMS) recomienda que ese porcentaje se quede por debajo del 5 %. La vacunación en Chile debiese llegar al menos a un 80 %.
        '''),
        html.H2(children="Indicadores"),
        dcc.Graph(
            id='indicators',
            figure=indicators_fig()
        ),
        html.H2(children="Tasa de positividad"),
        html.Div([
            dcc.Tabs(id="positivity-graph", value='positivity-graph-chile', children=[
                dcc.Tab(label='Chile', value='positivity-graph-chile'),
                dcc.Tab(label='Comunal', value='positivity-graph-communal'),
            ]),
            html.Div(id='positivity-graph-content')
        ]),
        html.H2(children="Vacunación en el territorio nacional"),
        dcc.Graph(
            id='general-vaccination',
            figure=country_vaccination_fig()
        ),
        html.H2(children="Última tasa de positividad"),
        html.Div([
            dcc.Tabs(id="positivity-choropleth", value='positivity-choropleth-rm', children=[
                dcc.Tab(label='Región Metropolitana', value='positivity-choropleth-rm'),
                dcc.Tab(label='Chile', value='positivity-choropleth-chile'),
            ]),
            html.Div(id='positivity-choropleth-content')
        ]),
        html.H2(children="Estado del programa paso a paso en la Región Metropolitana"),
        html.Span(
            [
                dbc.Badge("Cuarentena", pill=True, color="danger", className="mr-1"),
                dbc.Badge("Transición", pill=True, color="warning", className="mr-1"),
                dbc.Badge("Preparación", pill=True, color="yellow", className="mr-1", style={'background-color': 'yellow'}),
                dbc.Badge("Apertura inicial", pill=True, color="success", className="mr-1"),
            ]
        ),
        dcc.Graph(
            id='step',
            figure=step_fig()
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

@app.callback(dash.dependencies.Output('positivity-graph-content', 'children'),
              dash.dependencies.Input('positivity-graph', 'value'))
def render_content_positivity_graph(tab):
    if tab == 'positivity-graph-chile':
        return dcc.Graph(
            id='general-positivity',
            figure=country_positivity_fig_new()
        ),
    elif tab == 'positivity-graph-communal':
        return html.Div([
            dcc.Dropdown(
                options=commune_options,
                value=[],
                placeholder="Seleccione las comunas a visualizar",
                multi=True,
                id="commune-dropdown"
            ),
            dcc.Graph(id='graph-with-dropdown'),
        ]),

@app.callback(dash.dependencies.Output('positivity-choropleth-content', 'children'),
              dash.dependencies.Input('positivity-choropleth', 'value'))
def render_content_positivity_choropleth(tab):
    if tab == 'positivity-choropleth-rm':
        return dcc.Graph(
                id='choropleth',
                figure=choropleth_fig()
            )
    elif tab == 'positivity-choropleth-chile':
        return dcc.Graph(
                id='choropleth-country',
                figure=choropleth_country_fig()
            )

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
