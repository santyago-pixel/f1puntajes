# app.py - Final: CSV robusto, gráfico por evento (solo participantes >0), eventos hasta hoy,
# ignora primera fila de datos, standings sin ceros, historial completo.
import os
import csv
from io import StringIO
import html
import math
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

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
        # prefer comma if tie
        sep = max(counts, key=lambda k: (counts[k], k == ","))
    # probar lecturas con separadores detectados y fallback
    for s in [sep, ",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(StringIO(raw_text), sep=s)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    # intentar delim_whitespace como último recurso
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
            df = try_read_csv_from_text(raw)
            if df is not None:
                return df
        except Exception:
            continue
    return None

# -------- Inject CSS (optional) --------
def inject_css(file_name="style.css"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    css_path = os.path.join(base_dir, file_name)
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

inject_css("style.css")

# -------- Layout header --------
st.markdown('<div class="top-banner"><div class="container"><h1>F1 tabla de posiciones</h1></div></div>', unsafe_allow_html=True)
st.markdown('<div class="container">', unsafe_allow_html=True)

# -------- Load CSV --------
DATA_PATH = "data/scores.csv"
df = try_read_csv(DATA_PATH)

if df is None:
    st.error("No se pudo leer data/scores.csv o el archivo no existe en la ruta data/scores.csv. Subí un CSV válido en data/scores.csv o usa el uploader.")
    uploaded = st.file_uploader("Sube el CSV de puntajes (coma, tab, espacio)", type=["csv", "txt"])
    if uploaded is not None:
        try:
            content = uploaded.getvalue().decode("utf-8", errors="replace")
        except Exception:
            try:
                content = uploaded.getvalue().decode("latin-1", errors="replace")
            except Exception:
                content = None
        if content:
            df = try_read_csv_from_text(content)
    if df is None:
        st.stop()

# Normalize column names to strings
df.columns = df.columns.astype(str)

# Need at least 2 columns: Fecha, Lugar
if df.shape[1] < 2:
    st.error("El CSV debe tener al menos dos columnas: Fecha (col 1) y Lugar (col 2).")
    st.stop()

date_col = df.columns[0]
location_col = df.columns[1]
score_cols = df.columns[2:].tolist()

# Parse dates (dayfirst True to accept dd/mm/YYYY)
df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
df = df.sort_values(by=date_col).reset_index(drop=True)

# IGNORAR la primera fila de datos (no el header)
if len(df) > 0:
    df = df.iloc[1:].reset_index(drop=True)

# Validate after dropping
if df.shape[1] < 2 or df.shape[0] == 0:
    st.error("Después de ignorar la primera fila no hay suficientes datos. Asegurate del formato del CSV.")
    st.stop()

# Normalize location values
df[location_col] = df[location_col].astype(str)

# Convert score columns to numeric robustly (if exist)
if len(score_cols) == 0:
    st.warning("No se detectaron columnas de puntaje (no hay columnas después de la segunda). Se mostrará el historial con Fecha y Lugar.")
    scores = pd.DataFrame()
    cum = pd.DataFrame()
else:
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
    # prepare scores and cumulative
    scores = df.set_index(date_col)[score_cols].fillna(0).astype(float)
    cum = scores.cumsum()

# -------- Chart (first): eventos como eje X (categorical) --------
st.markdown("<h2>Puntaje a lo largo del tiempo</h2>", unsafe_allow_html=True)

if not cum.empty and cum.shape[1] > 0:
    # determinar 'hoy' en zona America/Argentina/Buenos_Aires si posible
    try:
        if ZoneInfo is not None:
            tz = ZoneInfo("America/Argentina/Buenos_Aires")
            today_ts = pd.Timestamp.now(tz=tz).normalize()
        else:
            today_ts = pd.Timestamp.now().normalize()
    except Exception:
        today_ts = pd.Timestamp.now().normalize()
    today_date = today_ts.date()

    # participantes con > 0 puntos en el último acumulado
    latest_totals = cum.iloc[-1]
    positive_names = latest_totals[latest_totals > 0].index.tolist()

    if len(positive_names) == 0:
        st.info("No hay participantes con puntos (todos tienen 0). El gráfico no se mostrará.")
    else:
        # formato 'long' solo para participantes positivos
        cum_pos = cum[positive_names].reset_index().melt(id_vars=[date_col], var_name="Name", value_name="Cumulative")
        cum_pos[date_col] = pd.to_datetime(cum_pos[date_col], errors="coerce")

        # preparar tabla de eventos para etiquetas (una fila por fecha)
        events = df[[date_col, location_col]].drop_duplicates(subset=[date_col]).sort_values(by=date_col).copy()
        events[date_col] = pd.to_datetime(events[date_col], errors="coerce")

        # etiquetar evento: parte antes de '/' y limpiar '-' extras
        def extract_event_label(loc):
            if not isinstance(loc, str) or loc.strip() == "":
                return ""
            part = loc.split("/")[0]
            part = part.split("-")[0].strip()
            return part

        events["Event"] = events[location_col].astype(str).apply(extract_event_label)

        # filtrar eventos hasta hoy
        events = events[events[date_col].notna()].copy()
        events = events[events[date_col].dt.date <= today_date]

        if events.empty:
            st.info("No hay eventos hasta la fecha actual para mostrar en el gráfico.")
        else:
            # envolver cum_pos con solo fechas presentes en events y participantes positivos
            cum_pos = cum_pos[cum_pos[date_col].notna()].copy()
            # normalizar fechas para merge
            cum_pos["__date_only"] = cum_pos[date_col].dt.normalize()
            events["__date_only"] = events[date_col].dt.normalize()

            # unir para traer la etiqueta Event
            merged = cum_pos.merge(events[["__date_only", "Event", location_col]], on="__date_only", how="inner")

            if merged.empty:
                st.info("Después de filtrar por fecha y participantes con puntos no quedan filas para graficar.")
            else:
                # orden de eventos por fecha (preservar primera aparición)
                events_order = events.sort_values(by=date_col)["Event"].tolist()
                seen = set()
                ordered_events = [x for x in events_order if not (x in seen or seen.add(x))]

                # ordenar participantes por total descendente para consistencia
                order = latest_totals[positive_names].sort_values(ascending=False).index.tolist()
                color_scale = alt.Color("Name:N", sort=order, legend=alt.Legend(title="Participante"))

                # crear gráfico: X categórica 'Event'
                chart = alt.Chart(merged).mark_line(interpolate="monotone").encode(
                    x=alt.X("Event:N", title="Evento (ubicación)", sort=ordered_events, axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("Cumulative:Q", title="Puntos acumulados"),
                    color=color_scale,
                    tooltip=[alt.Tooltip("__date_only:T", title="Fecha"), "Event:N", "Name:N", alt.Tooltip("Cumulative:Q", format=".2f")]
                ).properties(height=380)

                st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
                st.altair_chart(chart, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("No hay datos de puntaje suficientes para generar el gráfico.")

# -------- Standings (actuales) --------
st.markdown("<h2>Standings actuales</h2>", unsafe_allow_html=True)

if cum.empty or cum.shape[1] == 0:
    st.info("No hay standings para mostrar (faltan columnas de puntaje).")
else:
    latest = cum.iloc[-1].sort_values(ascending=False)
    # filtrar participantes con > 0 puntos
    latest_pos = latest[latest > 0]
    if latest_pos.empty:
        st.info("No hay participantes con puntos para mostrar en standings.")
    else:
        names = list(latest_pos.index)
        points = list(latest_pos.values.astype(float))
        total = len(names)
        per_col = 10
        cols = math.ceil(total / per_col)
        chunks = []
        for i in range(cols):
            start = i * per_col
            chunk = []
            for j in range(min(per_col, total - start)):
                idx = start + j
                rank = idx + 1
                chunk.append((rank, names[idx], points[idx]))
            chunks.append(chunk)

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
    # mostrar fecha como ISO para consistencia
    df_copy[date_col] = pd.to_datetime(df_copy[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    cols = [date_col, location_col] + score_cols
    thead = "<thead><tr>" + "".join([f"<th>{html.escape(str(c))}</th>" for c in cols]) + "</tr></thead>"
    rows_html = []
    for _, row in df_copy.iterrows():
        cells = []
        cells.append(f"<td>{html.escape(str(row[date_col]))}</td>")
        cells.append(f"<td>{html.escape(str(row[location_col]))}</td>")
        for sc in score_cols:
            try:
                v = float(row[sc])
                cell_text = str(int(v)) if v.is_integer() else str(round(v, 2))
            except Exception:
                cell_text = html.escape(str(row.get(sc, "")))
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
