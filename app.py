import streamlit as st
import pandas as pd
import altair as alt
from io import StringIO
import os
import html

st.set_page_config(page_title="Score Tracker", layout="wide")

# ---------- Inyectar CSS ----------
def inject_css(file_name="style.css"):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            css = f.read()
        # Inyectar la fuente y el CSS
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"style.css no encontrado en la raíz. Si querés el estilo exacto, subí {file_name}.")

inject_css("style.css")

# ---------- Estructura container (como tu HTML original) ----------
st.markdown('<div class="container">', unsafe_allow_html=True)

# Header (como en tu index.html)
st.markdown("""
<header>
  <h1>Score Tracker</h1>
  <p class="subtitle">Registro de puntajes por fecha — editá el CSV o subí uno nuevo para probar</p>
</header>
""", unsafe_allow_html=True)

# ---------- Cargar CSV ----------
@st.cache_data
def load_from_repo(path="data/scores.csv"):
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        return None

df = load_from_repo()

# Sidebar: Upload temporal
st.sidebar.header("Actualizar datos (prueba)")
uploaded = st.sidebar.file_uploader("Subir un CSV nuevo (sustituye temporalmente)", type=["csv"])
if uploaded is not None:
    content = uploaded.read().decode("utf-8")
    df = pd.read_csv(StringIO(content))
    st.sidebar.success("CSV cargado en memoria (no persiste).")

# ---------- Validaciones ----------
if df is None:
    st.markdown('<div class="loading">No se pudo leer <code>data/scores.csv</code>. Verificá que exista en el repo.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # cerrar container
    st.stop()

# Normalizar
df.columns = df.columns.astype(str)
date_col = df.columns[0]
df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
df = df.sort_values(by=date_col).reset_index(drop=True)

# Detectar columnas de score
score_cols = df.columns[1:].tolist()
if len(score_cols) == 0:
    st.markdown('<div class="error">No se detectaron columnas de puntaje (solo encontré la columna de fecha).</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# Forzar numérico en puntajes
for c in score_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

# ---------- Historial (tabla) ----------
st.markdown('<h2>Historial completo</h2>', unsafe_allow_html=True)

# Generar tabla HTML con clases
def df_to_html_table(df_in, date_col):
    # Convertir la fecha a string legible
    df_copy = df_in.copy()
    df_copy[date_col] = df_copy[date_col].dt.strftime("%Y-%m-%d")
    # Escapar contenido para evitar inyecciones
    html_table = df_copy.to_html(index=False, classes="", table_id="score-table", justify="left", border=0)
    # Wrap con el wrapper que tiene fondo / borde en CSS
    return f'<div class="table-wrapper">{html_table}</div>'

table_html = df_to_html_table(df, date_col)
st.markdown(table_html, unsafe_allow_html=True)

# ---------- Standings actuales (lista) ----------
st.markdown('<h2>Standings actuales</h2>', unsafe_allow_html=True)

scores = df.set_index(date_col)[score_cols].fillna(0).astype(float)
cum = scores.cumsum()

if cum.shape[0] == 0:
    st.markdown('<div class="loading">No hay registros para calcular standings.</div>', unsafe_allow_html=True)
else:
    latest = cum.iloc[-1].sort_values(ascending=False)
    # Construir lista HTML con clases
    list_items = []
    for i, (name, pts) in enumerate(latest.items(), start=1):
        safe_name = html.escape(str(name))
        safe_pts = html.escape(str(int(pts) if pts==int(pts) else round(float(pts),2)))
        rank_class = "standings-item"
        # marcar top1/2/3
        if i == 1:
            rank_class += " standings-top1"
        elif i == 2:
            rank_class += " standings-top2"
        elif i == 3:
            rank_class += " standings-top3"
        item_html = f'<li class="{rank_class}"><div class="standings-name">{safe_name}</div><div class="standings-score">{safe_pts}</div></li>'
        list_items.append(item_html)
    list_html = '<ul class="standings-list">' + "\n".join(list_items) + '</ul>'
    st.markdown(list_html, unsafe_allow_html=True)

# ---------- Chart ----------
st.markdown('<h2>Puntaje a lo largo del tiempo</h2>', unsafe_allow_html=True)

if cum.shape[0] > 0:
    cum_reset = cum.reset_index().melt(id_vars=[date_col], var_name="Name", value_name="Cumulative")
    # Altair requiere columna de fecha tipo datetime
    cum_reset[date_col] = pd.to_datetime(cum_reset[date_col])
    chart = alt.Chart(cum_reset).mark_line().encode(
        x=alt.X(date_col, title="Date", axis=alt.Axis(format='%Y-%m-%d')),
        y=alt.Y("Cumulative", title="Cumulative points"),
        color=alt.Color("Name:N", legend=alt.Legend(title="Name")),
        tooltip=[date_col, "Name", "Cumulative"]
    ).properties(height=360)
    # Wrap chart in .chart-wrapper container
    st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
    st.altair_chart(chart, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="loading">No hay datos para graficar.</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
<footer>
  <p>Hecho con Streamlit — estilos adaptados desde tu sitio original.</p>
</footer>
""", unsafe_allow_html=True)

# cerrar container
st.markdown('</div>', unsafe_allow_html=True)
