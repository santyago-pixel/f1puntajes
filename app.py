# app.py - Versión final ajustada: F1 tabla de posiciones, título blanco, tabla y standings con color de fechas, sin sidebar
import os
import csv
from io import StringIO
import html

import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="F1 tabla de posiciones", layout="wide")

# ----------------- UTIL: leer CSV detectando separador y encoding -----------------
def try_read_csv_from_text(raw_text):
    if not raw_text:
        return None
    try:
        sample = raw_text[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        sep = dialect.delimiter
    except Exception:
        header_line = raw_text.splitlines()[0] if raw_text.splitlines() else ""
        counts = {",": header_line.count(","), ";": header_line.count(";"), "\t": header_line.count("\t"), "|": header_line.count("|")}
        sep = max(counts, key=counts.get)
    candidates = [sep, ",", ";", "\t", "|"]
    for s in candidates:
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
    raw = None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                raw = f.read()
            break
        except Exception:
            raw = None
    if raw is None:
        return None
    return try_read_csv_from_text(raw)

# ----------------- Inyectar CSS -----------------
def inject_css(file_name="style.css"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    css_path = os.path.join(base_dir, file_name)
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.warning("style.css no encontrado en la raíz. Subí style.css para aplicar el tema.")

inject_css("style.css")

# ----------------- Session state para paste-on-demand -----------------
if "show_paste" not in st.session_state:
    st.session_state.show_paste = False
if "pasted_text" not in st.session_state:
    st.session_state.pasted_text = ""

# ----------------- Layout: banner + container -----------------
st.markdown('<div class="top-banner"><div class="container"><header><h1>F1 tabla de posiciones</h1></header></div></div>', unsafe_allow_html=True)
st.markdown('<div class="container">', unsafe_allow_html=True)

# ----------------- Cargar CSV inicial -----------------
DATA_PATH = "data/scores.csv"

@st.cache_data
def load_scores_file(path=DATA_PATH):
    return try_read_csv(path)

df = load_scores_file(DATA_PATH)

# ----------------- Mostrar mensaje informativo (en la página principal en lugar de sidebar) -----------------
st.markdown('<div class="muted">Para persistir cambios en la web, subí un CSV (CSV UTF-8, comma delimited) al repo en GitHub. Usa el botón al final para pegar desde Excel y cargar en memoria.</div>', unsafe_allow_html=True)

# ----------------- Si hay pasted_text en sesión, procesar y notificar en la página -----------------
if st.session_state.pasted_text:
    parsed = try_read_csv_from_text(st.session_state.pasted_text)
    if parsed is not None:
        df = parsed
        st.success("Datos pegados cargados en memoria.")
    else:
        st.error("Los datos pegados no pudieron parsearse. Revisá el formato.")

# ----------------- Validaciones y normalización -----------------
if df is None:
    st.markdown('<div class="loading">No se pudo leer <code>data/scores.csv</code>. Subí el archivo al repo o pega datos usando el botón al final.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

df.columns = df.columns.astype(str)
date_col = df.columns[0]
df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
df = df.sort_values(by=date_col).reset_index(drop=True)

score_cols = df.columns[1:].tolist()
if len(score_cols) == 0:
    st.markdown('<div class="error">No se detectaron columnas de puntaje (solo encontré la columna de fecha).</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

for c in score_cols:
    series = pd.to_numeric(df[c], errors="coerce")
    na_ratio = series.isna().sum() / max(1, len(series))
    if na_ratio > 0.3:
        temp = df[c].astype(str).str.replace(".", "", regex=False)
        temp = temp.str.replace(",", ".", regex=False)
        try:
            series2 = pd.to_numeric(temp, errors="coerce")
            if series2.isna().sum() < series.isna().sum():
                series = series2
        except Exception:
            pass
    df[c] = series.fillna(0)

# ----------------- Prepare cumulative scores -----------------
scores = df.set_index(date_col)[score_cols].fillna(0).astype(float)
cum = scores.cumsum()

# ----------------- Chart (primero) -----------------
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

# ----------------- Standings (arriba of historial) -----------------
st.markdown('<h2>Standings actuales</h2>', unsafe_allow_html=True)
if cum.shape[0] == 0:
    st.markdown('<div class="loading">No hay registros para calcular standings.</div>', unsafe_allow_html=True)
else:
    latest = cum.iloc[-1].sort_values(ascending=False)
    list_items = []
    for i, (name, pts) in enumerate(latest.items(), start=1):
        safe_name = html.escape(str(name))
        try:
            pts_val = float(pts)
            pts_text = str(int(pts_val)) if pts_val.is_integer() else str(round(pts_val, 2))
        except Exception:
            pts_text = str(pts)
        safe_pts = html.escape(pts_text)
        rank_class = "standings-item"
        if i == 1:
            rank_class += " standings-top1"
        elif i == 2:
            rank_class += " standings-top2"
        elif i == 3:
            rank_class += " standings-top3"
        score_class = "standings-score" if float(pts) != 0 else "standings-score score-zero"
        item_html = f'<li class="{rank_class}"><div class="standings-name">{safe_name}</div><div class="{score_class}">{safe_pts}</div></li>'
        list_items.append(item_html)
    list_html = '<ul class="standings-list">' + "\n".join(list_items) + '</ul>'
    st.markdown(list_html, unsafe_allow_html=True)

# ----------------- Historial completo (tabla) -----------------
st.markdown('<h2>Historial completo</h2>', unsafe_allow_html=True)

def df_to_html_table_improved(df_in, date_col):
    df_copy = df_in.copy()
    df_copy[date_col] = df_copy[date_col].dt.strftime("%Y-%m-%d")
    cols = df_copy.columns.tolist()
    thead = "<thead><tr>" + "".join([f"<th>{html.escape(c)}</th>" for c in cols]) + "</tr></thead>"
    rows_html = []
    for _, row in df_copy.iterrows():
        cells = []
        for ci, c in enumerate(cols):
            val = row[c]
            if ci == 0:
                cell = f'<td>{html.escape(str(val))}</td>'
            else:
                try:
                    v = float(val)
                    cell_text = str(int(v)) if v.is_integer() else str(round(v, 2))
                except Exception:
                    cell_text = html.escape(str(val))
                cell = f'<td class="numeric">{cell_text}</td>'
            cells.append(cell)
        rows_html.append("<tr>" + "".join(cells) + "</tr>")
    tbody = "<tbody>" + "\n".join(rows_html) + "</tbody>"
    table_html = f"<table>{thead}{tbody}</table>"
    return f'<div class="table-wrapper">{table_html}</div>'

table_html = df_to_html_table_improved(df, date_col)
st.markdown(table_html, unsafe_allow_html=True)

# ----------------- Paste-on-demand button at bottom -----------------
st.markdown("<hr/>", unsafe_allow_html=True)
if st.button("Editar / Pegar datos desde Excel"):
    st.session_state.show_paste = True

if st.session_state.show_paste:
    st.markdown("""
    <div style="margin-top:0.5rem;margin-bottom:0.6rem;">
      <strong>O pega aquí datos copiados desde Excel (tabs o comas)</strong>
      <div class="muted" style="margin-top:0.15rem;">Copiá incluyendo la fila de encabezado (Date, Nombre1, Nombre2...). Luego presioná "Cargar datos pegados".</div>
    </div>
    """, unsafe_allow_html=True)
    pasted_area = st.text_area("", value=st.session_state.pasted_text, height=180, key="paste_area_final")
    if st.button("Cargar datos pegados"):
        raw = pasted_area or ""
        parsed = try_read_csv_from_text(raw)
        if parsed is not None:
            st.session_state.pasted_text = raw
            st.experimental_rerun()
        else:
            st.error("No se pudo parsear el texto pegado. Asegurate de incluir el header y copiar desde Excel (Ctrl+C).")

# ----------------- Footer -----------------
st.markdown("""
<footer>
  <p>Hecho con Streamlit.</p>
</footer>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
