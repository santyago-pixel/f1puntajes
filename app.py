# app.py - Versión final: ignora la primera fila de datos, segunda columna = Lugar,
# gráfico antes del historial, standings en columnas de hasta 10 filas
import os
import csv
from io import StringIO
import html
import math

import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="F1 tabla de posiciones", layout="wide")

# -------- CSV robusto (lectura) --------
def try_read_csv_from_text(raw_text):
    if not raw_text:
        return None
    try:
        sample = raw_text[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        sep = dialect.delimiter
    except Exception:
        header_line = raw_text.splitlines()[0] if raw_text.splitlines() else ""
        counts = {
            ",": header_line.count(","),
            ";": header_line.count(";"),
            "\t": header_line.count("\t"),
            "|": header_line.count("|"),
        }
        sep = max(counts, key=counts.get)
    for s in [sep, ",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(StringIO(raw_text), sep=s)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    try:
        df = pd.read_csv(StringIO(raw_text), delim_whitespace=True)
        if df.shape[1] > 1:
            return df
    except Exception:
        pass
    return None

def try_read_csv(path):
    if not os.path.exists(path):
        return None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                raw = f.read()
            return try_read_csv_from_text(raw)
        except Exception:
            continue
    return None

# -------- Inject CSS (style.css must be in same folder) --------
def inject_css(file_name="style.css"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    css_path = os.path.join(base_dir, file_name)
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

inject_css("style.css")

# -------- Layout: banner + container --------
st.markdown('<div class="top-banner"><div class="container"><h1>F1 tabla de posiciones</h1></div></div>', unsafe_allow_html=True)
st.markdown('<div class="container">', unsafe_allow_html=True)

# -------- Load CSV --------
DATA_PATH = "data/scores.csv"
df = try_read_csv(DATA_PATH)

if df is None:
    st.error("No se pudo leer data/scores.csv o el archivo no existe en la ruta data/scores.csv")
    st.stop()

# Ensure columns are strings
df.columns = df.columns.astype(str)

# Must have at least Fecha and Lugar; puntajes desde la 3ra columna (pero permitimos que no haya puntajes)
if df.shape[1] < 2:
    st.error("El CSV debe tener al menos dos columnas: Fecha y Lugar. Añadí columnas de puntaje después.")
    st.stop()

date_col = df.columns[0]
location_col = df.columns[1]
score_cols = df.columns[2:].tolist()  # a partir de la 3ra columna están los puntajes

# Parse dates (assume dayfirst like dd/mm/YYYY)
df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
df = df.sort_values(by=date_col).reset_index(drop=True)

# ---- IGNORAR la primera fila de datos (fila 1 del Excel) ----
# Esto quita la primera fila *de datos* (no el header).
if len(df) > 0:
    df = df.iloc[1:].reset_index(drop=True)

# Validate after dropping: still need at least Fecha+Lugar
if df.shape[1] < 2 or df.shape[0] == 0:
    st.error("Después de ignorar la primera fila no hay suficientes datos. Asegurate del formato CSV.")
    st.stop()

# Normalize location as string
df[location_col] = df[location_col].astype(str)

# If there are no score columns, warn (we will still show historial with date+location)
if len(score_cols) == 0:
    st.warning("No se detectaron columnas de puntaje (no hay columnas después de la segunda). Se mostrará el historial con Fecha y Lugar, pero no habrá standings ni gráfico.")
else:
    # Convert score columns to numeric robustly
    for c in score_cols:
        series = pd.to_numeric(df[c], errors="coerce")
        na_ratio = series.isna().sum() / max(1, len(series))
        if na_ratio > 0.3:
            # intentar limpiar: quitar separador miles y cambiar coma decimal por punto
            temp = df[c].astype(str).str.replace(".", "", regex=False)
            temp = temp.str.replace(",", ".", regex=False)
            try:
                series2 = pd.to_numeric(temp, errors="coerce")
                if series2.isna().sum() < series.isna().sum():
                    series = series2
            except Exception:
                pass
        df[c] = series.fillna(0)

# Prepare cumulative and scores only if score_cols exist
if len(score_cols) > 0:
    # set_index uses date_col; ensure unique index handled by reset when needed
    scores = df.set_index(date_col)[score_cols].fillna(0).astype(float)
    cum = scores.cumsum()
else:
    scores = pd.DataFrame()
    cum = pd.DataFrame()

# -------- Chart (first) --------
st.markdown("<h2>Puntaje a lo largo del tiempo</h2>", unsafe_allow_html=True)
if not cum.empty and cum.shape[1] > 0:
    cum_reset = cum.reset_index().melt(id_vars=[date_col], var_name="Name", value_name="Cumulative")
    cum_reset[date_col] = pd.to_datetime(cum_reset[date_col])
    chart = alt.Chart(cum_reset).mark_line().encode(
        x=alt.X(date_col, title="Fecha", axis=alt.Axis(format='%Y-%m-%d')),
        y=alt.Y("Cumulative", title="Puntos acumulados"),
        color=alt.Color("Name:N", legend=alt.Legend(title="Participante")),
        tooltip=[date_col, "Name", "Cumulative"]
    ).properties(height=360)
    st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
    st.altair_chart(chart, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("No hay datos de puntaje suficientes para generar el gráfico.")

# -------- Standings (above the history) --------
st.markdown("<h2>Standings actuales</h2>", unsafe_allow_html=True)

if cum.empty or cum.shape[1] == 0:
    st.info("No hay standings para mostrar (faltan columnas de puntaje).")
else:
    latest = cum.iloc[-1].sort_values(ascending=False)
    names = list(latest.index)
    points = list(latest.values.astype(float))
    total = len(names)
    # chunk into groups of max 10 per column
    per_col = 10
    cols = math.ceil(total / per_col)
    chunks = []
    for i in range(cols):
        start = i * per_col
        end = start + per_col
        chunk = []
        for j in range(min(per_col, total - start)):
            idx = start + j
            rank = idx + 1
            chunk.append((rank, names[idx], points[idx]))
        chunks.append(chunk)

    # Build HTML with columns side by side
    html_cols = ['<div class="standings-columns">']
    for chunk in chunks:
        items = []
        for rank, nm, pts in chunk:
            safe_name = html.escape(str(nm))
            try:
                pts_val = float(pts)
                pts_text = str(int(pts_val)) if pts_val.is_integer() else str(round(pts_val, 2))
            except Exception:
                pts_text = html.escape(str(pts))
            item_html = (
                f'<li class="standings-item">'
                f'<div class="standings-rank">{rank}.</div>'
                f'<div class="standings-name">{safe_name}</div>'
                f'<div class="standings-score">{pts_text}</div>'
                f'</li>'
            )
            items.append(item_html)
        list_html = '<ul class="standings-list">' + "\n".join(items) + '</ul>'
        html_cols.append(list_html)
    html_cols.append('</div>')
    st.markdown("\n".join(html_cols), unsafe_allow_html=True)

# -------- Historial completo (Fecha | Lugar | scores) --------
st.markdown("<h2>Historial completo</h2>", unsafe_allow_html=True)

def df_to_html_table_with_location(df_in, date_col, location_col, score_cols):
    df_copy = df_in.copy()
    df_copy[date_col] = df_copy[date_col].dt.strftime("%Y-%m-%d")
    cols = [date_col, location_col] + score_cols
    thead = "<thead><tr>" + "".join([f"<th>{html.escape(str(c))}</th>" for c in cols]) + "</tr></thead>"
    rows_html = []
    for _, row in df_copy.iterrows():
        cells = []
        # Fecha
        cells.append(f"<td>{html.escape(str(row[date_col]))}</td>")
        # Lugar
        cells.append(f"<td>{html.escape(str(row[location_col]))}</td>")
        # Puntajes (si hay)
        for sc in score_cols:
            try:
                v = float(row[sc])
                cell_text = str(int(v)) if v.is_integer() else str(round(v, 2))
            except Exception:
                cell_text = html.escape(str(row[sc]))
            cells.append(f'<td class="numeric">{cell_text}</td>')
        rows_html.append("<tr>" + "".join(cells) + "</tr>")
    tbody = "<tbody>" + "\n".join(rows_html) + "</tbody>"
    table_html = f"<table id='score-table'>{thead}{tbody}</table>"
    return f'<div class="table-wrapper">{table_html}</div>'

st.markdown(df_to_html_table_with_location(df, date_col, location_col, score_cols), unsafe_allow_html=True)

# -------- Footer --------
st.markdown("""
<footer>
  <p>Hecho con Streamlit.</p>
</footer>
""", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
