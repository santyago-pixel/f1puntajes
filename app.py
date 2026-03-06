# app.py - versión robusta para detectar separador y encodings automáticamente
import os
import csv
from io import StringIO
import html

import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="Score Tracker", layout="wide")


# ----------------- UTIL: leer CSV detectando separador y encoding -----------------
def try_read_csv(path):
    """
    Leer un CSV intentando detectar:
      - encoding (utf-8, latin-1, cp1252)
      - separador (',', ';', '\t', '|')
    Devuelve DataFrame o None si falla.
    """
    if not os.path.exists(path):
        return None

    # 1) Leer raw probando distintos encodings
    raw = None
    used_encoding = None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                raw = f.read()
            used_encoding = enc
            break
        except Exception:
            raw = None
    if raw is None:
        return None

    # 2) Detectar separador con csv.Sniffer sobre una muestra
    sep = None
    try:
        sample = raw[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        sep = dialect.delimiter
    except Exception:
        # fallback: contar delimitadores en la primera línea
        first_line = raw.splitlines()[0] if raw.splitlines() else ""
        counts = {",": first_line.count(","), ";": first_line.count(";"), "\t": first_line.count("\t"), "|": first_line.count("|")}
        sep = max(counts, key=counts.get)

    # 3) Intentar leer con pandas usando el separador detectado; si falla, probar fallbacks
    tried = []
    candidates = [sep, ",", ";", "\t", "|"]
    for s in candidates:
        if s in tried:
            continue
        tried.append(s)
        try:
            df = pd.read_csv(StringIO(raw), sep=s)
            # Si pandas detecta sólo 1 columna, seguir probando otros separadores
            if df.shape[1] <= 1:
                continue
            return df
        except Exception:
            continue

    # 4) Como último recurso, intentar leer con delim_whitespace=True (espacios/tabulación)
    try:
        df = pd.read_csv(StringIO(raw), delim_whitespace=True)
        if df.shape[1] > 1:
            return df
    except Exception:
        pass

    # Si todo falla:
    return None


# ----------------- Inyectar CSS si existe -----------------
def inject_css(file_name="style.css"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    css_path = os.path.join(base_dir, file_name)
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"style.css no encontrado en la raíz. Si querés el estilo exacto, subí style.css.")


inject_css("style.css")


# ----------------- Estructura (container similar al HTML original) -----------------
st.markdown('<div class="container">', unsafe_allow_html=True)
st.markdown("""
<header>
  <h1>Score Tracker</h1>
  <p class="subtitle">Registro de puntajes por fecha — editá el CSV o pegá datos (se detecta separador)</p>
</header>
""", unsafe_allow_html=True)


# ----------------- Cargar CSV (robusto) -----------------
DATA_PATH = "data/scores.csv"

@st.cache_data
def load_scores(path=DATA_PATH):
    return try_read_csv(path)

df = load_scores(DATA_PATH)


# Sidebar: permitir pegar datos directamente (opcional) o subir archivo
st.sidebar.header("Actualizar datos (prueba)")
uploaded = st.sidebar.file_uploader("Subir un CSV nuevo (sustituye temporalmente)", type=["csv"])
pasted = st.sidebar.text_area("O pega aquí datos copiados desde Excel (tabs o comas)", height=120)

if uploaded is not None:
    # si suben un archivo, leer desde el buffer (también detecta separador)
    raw = uploaded.getvalue().decode("utf-8", errors="ignore")
    # intentar detectar separador en el texto pegado
    try:
        dialect = csv.Sniffer().sniff(raw[:8192], delimiters=[",", ";", "\t", "|"])
        sep = dialect.delimiter
    except Exception:
        # heurística
        header_line = raw.splitlines()[0] if raw.splitlines() else ""
        counts = {",": header_line.count(","), ";": header_line.count(";"), "\t": header_line.count("\t"), "|": header_line.count("|")}
        sep = max(counts, key=counts.get)
    try:
        df = pd.read_csv(StringIO(raw), sep=sep)
        st.sidebar.success("CSV subido y cargado en memoria (no persiste).")
    except Exception:
        df = None
        st.sidebar.error("No se pudo leer el CSV subido.")
elif pasted.strip():
    # si pegan en el textarea, procesar texto
    raw = pasted
    try:
        dialect = csv.Sniffer().sniff(raw[:8192], delimiters=[",", ";", "\t", "|"])
        sep = dialect.delimiter
    except Exception:
        header_line = raw.splitlines()[0] if raw.splitlines() else ""
        counts = {",": header_line.count(","), ";": header_line.count(";"), "\t": header_line.count("\t"), "|": header_line.count("|")}
        sep = max(counts, key=counts.get)
    try:
        df = pd.read_csv(StringIO(raw), sep=sep)
        st.sidebar.success("Texto pegado detectado y cargado en memoria (no persiste).")
    except Exception:
        df = None
        st.sidebar.error("No se pudo parsear el texto pegado. Si copiaste desde Excel, asegurate de incluir el header.")


# ----------------- Validaciones y normalización -----------------
if df is None:
    st.markdown('<div class="loading">No se pudo leer <code>data/scores.csv</code>. Verificá que exista o subí/pegá datos en la barra lateral.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# Forzar columnas como strings y detectar columna de fecha como la primera
df.columns = df.columns.astype(str)
date_col = df.columns[0]

# Interpretar fechas con dayfirst=True (formato dd/mm/YYYY común en tu ejemplo)
df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
df = df.sort_values(by=date_col).reset_index(drop=True)

# Detectar columnas de puntuación (todas menos la primera)
score_cols = df.columns[1:].tolist()
if len(score_cols) == 0:
    st.markdown('<div class="error">No se detectaron columnas de puntaje (solo encontré la columna de fecha).</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# Convertir columnas de puntaje a numérico de forma robusta:
for c in score_cols:
    # Primer intento directo
    series = pd.to_numeric(df[c], errors="coerce")
    # Si demasiados NaN, intentar reemplazar coma decimal por punto (por si subiste "1,0" como decimal)
    na_ratio = series.isna().sum() / max(1, len(series))
    if na_ratio > 0.3:  # heurística: si >30% quedaron NaN, intentar limpiar formateos
        temp = df[c].astype(str).str.replace(".", "", regex=False)  # intenta quitar separador de miles
        temp = temp.str.replace(",", ".", regex=False)  # convertir coma decimal a punto
        series2 = pd.to_numeric(temp, errors="coerce")
        # Si series2 tiene menos NaN, usarlo
        if series2.isna().sum() < series.isna().sum():
            series = series2
    # Finalmente rellenar NaN con 0 (asumimos que ausencia = 0 puntos)
    df[c] = series.fillna(0)

# ----------------- Mostrar Historial -----------------
st.markdown('<h2>Historial completo</h2>', unsafe_allow_html=True)

def df_to_html_table(df_in, date_col):
    df_copy = df_in.copy()
    # Formatear fechas legibles (si no son NaT)
    df_copy[date_col] = df_copy[date_col].dt.strftime("%Y-%m-%d")
    html_table = df_copy.to_html(index=False, classes="", table_id="score-table", justify="left", border=0)
    return f'<div class="table-wrapper">{html_table}</div>'

table_html = df_to_html_table(df, date_col)
st.markdown(table_html, unsafe_allow_html=True)

# ----------------- Standings actuales -----------------
st.markdown('<h2>Standings actuales</h2>', unsafe_allow_html=True)

scores = df.set_index(date_col)[score_cols].fillna(0).astype(float)
cum = scores.cumsum()

if cum.shape[0] == 0:
    st.markdown('<div class="loading">No hay registros para calcular standings.</div>', unsafe_allow_html=True)
else:
    latest = cum.iloc[-1].sort_values(ascending=False)
    list_items = []
    for i, (name, pts) in enumerate(latest.items(), start=1):
        safe_name = html.escape(str(name))
        # Si el número es entero mostrado como int
        try:
            pts_val = float(pts)
            safe_pts = html.escape(str(int(pts_val)) if pts_val.is_integer() else str(round(pts_val, 2)))
        except Exception:
            safe_pts = html.escape(str(pts))
        rank_class = "standings-item"
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

# ----------------- Chart -----------------
st.markdown('<h2>Puntaje a lo largo del tiempo</h2>', unsafe_allow_html=True)

if cum.shape[0] > 0:
    cum_reset = cum.reset_index().melt(id_vars=[date_col], var_name="Name", value_name="Cumulative")
    cum_reset[date_col] = pd.to_datetime(cum_reset[date_col])
    chart = alt.Chart(cum_reset).mark_line().encode(
        x=alt.X(date_col, title="Date", axis=alt.Axis(format='%Y-%m-%d')),
        y=alt.Y("Cumulative", title="Cumulative points"),
        color=alt.Color("Name:N", legend=alt.Legend(title="Name")),
        tooltip=[date_col, "Name", "Cumulative"]
    ).properties(height=360)
    st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
    st.altair_chart(chart, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="loading">No hay datos para graficar.</div>', unsafe_allow_html=True)

# ----------------- Footer y cierre de container -----------------
st.markdown("""
<footer>
  <p>Hecho con Streamlit — estilos adaptados desde tu sitio original.</p>
</footer>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
