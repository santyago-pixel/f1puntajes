# app.py - Final actualizado: historial sin ceros (blanco) y cuadriculado suave
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

# -------- CSS inyectado (incluye cuadriculado suave para la tabla) --------
INLINE_CSS = """
/* Contenedor */
.container { max-width: 1200px; margin: 0 auto; padding: 10px; }

/* Top banner */
.top-banner { background: linear-gradient(90deg,#111827,#1f2937); color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }
.top-banner h1 { margin: 0; font-size: 20px; font-weight: 600; }

/* Chart wrapper */
.chart-wrapper { background: #fff; padding: 8px; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }

/* Standings columns */
.standings-columns { display:flex; gap:24px; align-items:flex-start; margin: 12px 0; }
.standings-list { list-style:none; padding: 0; margin: 0; width: 220px; }
.standings-item { display:flex; align-items:center; gap:8px; padding:6px 4px; border-bottom: 1px solid rgba(0,0,0,0.03); }
.standings-rank { width:28px; font-weight:600; color:#111827; }
.standings-name { flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.standings-score { min-width:48px; text-align:right; font-weight:600; }

/* Tabla historial con cuadriculado suave */
.table-wrapper { overflow-x:auto; margin-top:12px; }
#score-table { width:100%; border-collapse: collapse; font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }
#score-table thead th { text-align:left; padding:8px; border-bottom:2px solid rgba(0,0,0,0.06); background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(250,250,250,0.9)); position: sticky; top:0; z-index:1; }
#score-table tbody td { padding:8px; border-bottom:1px solid rgba(0,0,0,0.04); }
#score-table tbody tr:nth-child(even) td { background: rgba(0,0,0,0.01); } /* cuadriculado suave */
#score-table td.numeric { text-align:right; font-feature-settings: "tnum"; }

/* Ajustes responsivos */
@media (max-width:800px) {
  .standings-columns { flex-direction:column; gap:12px; }
}
"""
st.markdown(f"<style>{INLINE_CSS}</style>", unsafe_allow_html=True)

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
        sep = max(counts, key=lambda k: (counts[k], k == ","))
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
            df = try_read_csv_from_text(raw)
            if df is not None:
                return df
        except Exception:
            continue
    return None

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
    scores = df.set_index(date_col)[score_cols].fillna(0).astype(float)
    cum = scores.cumsum()

# -------- Chart (first): eventos como eje X (categorical) --------
st.markdown("<h2>Puntaje a lo largo del tiempo</h2>", unsafe_allow_html=True)

if not cum.empty and cum.shape[1] > 0:
    try:
        if ZoneInfo is not None:
            tz = ZoneInfo("America/Argentina/Buenos_Aires")
            today_ts = pd.Timestamp.now(tz=tz).normalize()
        else:
            today_ts = pd.Timestamp.now().normalize()
    except Exception:
        today_ts = pd.Timestamp.now().normalize()
    today_date = today_ts.date()

    latest_totals = cum.iloc[-1]
    positive_names = latest_totals[latest_totals > 0].index.tolist()

    if len(positive_names) == 0:
        st.info("No hay participantes con puntos (todos tienen 0). El gráfico no se mostrará.")
    else:
        cum_pos = cum[positive_names].reset_index().melt(id_vars=[date_col], var_name="Name", value_name="Cumulative")
        cum_pos[date_col] = pd.to_datetime(cum_pos[date_col], errors="coerce")

        events = df[[date_col, location_col]].drop_duplicates(subset=[date_col]).sort_values(by=date_col).copy()
        events[date_col] = pd.to_datetime(events[date_col], errors="coerce")

        def extract_event_label(loc):
            if not isinstance(loc, str) or loc.strip() == "":
                return ""
            part = loc.split("/")[0]
            part = part.split("-")[0].strip()
            return part

        events["Event"] = events[location_col].astype(str).apply(extract_event_label)
        events = events[events[date_col].notna()].copy()
        events = events[events[date_col].dt.date <= today_date]

        if events.empty:
            st.info("No hay eventos hasta la fecha actual para mostrar en el gráfico.")
        else:
            cum_pos = cum_pos[cum_pos[date_col].notna()].copy()
            cum_pos["__date_only"] = cum_pos[date_col].dt.normalize()
            events["__date_only"] = events[date_col].dt.normalize()
            merged = cum_pos.merge(events[["__date_only", "Event", location_col]], on="__date_only", how="inner")

            if merged.empty:
                st.info("Después de filtrar por fecha y participantes con puntos no quedan filas para graficar.")
            else:
                events_order = events.sort_values(by=date_col)["Event"].tolist()
                seen = set()
                ordered_events = [x for x in events_order if not (x in seen or seen.add(x))]

                order = latest_totals[positive_names].sort_values(ascending=False).index.tolist()
                color_scale = alt.Color("Name:N", sort=order, legend=alt.Legend(title="Participante"))

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
    df_copy[date_col] = pd.to_datetime(df_copy[date_col], errors="coerce").dt.strftime("%Y-%m-%d")

    cols = [date_col, location_col] + score_cols

    thead = "<thead><tr>"
    for c in cols:
        thead += f"<th style='text-align:left;padding:6px;border-bottom:1px solid #ddd'>{html.escape(str(c))}</th>"
    thead += "</tr></thead>"

    rows_html = []

    for _, row in df_copy.iterrows():
        cells = []

        # Fecha
        cells.append(f"<td style='padding:6px'>{html.escape(str(row[date_col]))}</td>")

        # Lugar
        cells.append(f"<td style='padding:6px'>{html.escape(str(row[location_col]))}</td>")

        # Puntajes
        for sc in score_cols:
            cell_text = ""

            try:
                v = float(row.get(sc, 0))
                if v > 0:
                    cell_text = str(int(v)) if v.is_integer() else str(round(v, 2))
            except Exception:
                pass

            cells.append(f"<td style='padding:6px;text-align:right'>{cell_text}</td>")

        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    tbody = "<tbody>" + "\n".join(rows_html) + "</tbody>"

    table_html = f"""
    <table id="score-table" style="width:100%;border-collapse:collapse">
        {thead}
        {tbody}
    </table>
    """

    return f'<div class="table-wrapper">{table_html}</div>'
    df_copy = df_in.copy()
    df_copy[date_col] = pd.to_datetime(df_copy[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    cols = [date_col, location_col] + score_cols
    thead = "<thead><tr>" + "".join([f"<th>{html.escape(str(c))}</th>" for c in cols]) + "</tr></thead>"
    rows_html = []
    for _, row in df_copy.iterrows():
        cells = []
        # Fecha
        cells.append(f"<td>{html.escape(str(row[date_col]))}</td>")
        # Lugar
        cells.append(f"<td>{html.escape(str(row[location_col]))}</td>")
        # Puntajes: mostrar solo si > 0, sino dejar en blanco
        for sc in score_cols:
            cell_text = ""
            try:
                v = float(row.get(sc, 0))
                if v > 0:
                    cell_text = str(int(v)) if v.is_integer() else str(round(v, 2))
            except Exception:
                # si no es numérico, dejarlo tal cual si no está vacío; si está vacío, dejar blanco
                raw = row.get(sc, "")
                if raw is not None and str(raw).strip() not in ["", "nan", "None"]:
                    cell_text = html.escape(str(raw))
                else:
                    cell_text = ""
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
