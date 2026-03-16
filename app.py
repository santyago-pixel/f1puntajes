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

# -------- Layout --------
st.markdown("# F1 tabla de posiciones")

DATA_PATH = "data/scores.csv"
df = try_read_csv(DATA_PATH)

if df is None:
    st.error("No se pudo leer data/scores.csv")
    st.stop()

df.columns = df.columns.astype(str)

date_col = df.columns[0]
location_col = df.columns[1]
score_cols = df.columns[2:].tolist()

df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
df = df.sort_values(by=date_col).reset_index(drop=True)

# ignorar primera fila de datos
if len(df) > 0:
    df = df.iloc[1:].reset_index(drop=True)

df[location_col] = df[location_col].astype(str)

# convertir puntajes
for c in score_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

scores = df.set_index(date_col)[score_cols].fillna(0).astype(float)
cum = scores.cumsum()

# -------- Chart --------
st.markdown("## Puntaje a lo largo del tiempo")

if not cum.empty:

    today = pd.Timestamp.now().date()

    latest_totals = cum.iloc[-1]
    positive_names = latest_totals[latest_totals > 0].index.tolist()

    cum_pos = cum[positive_names].reset_index().melt(
        id_vars=[date_col], var_name="Name", value_name="Cumulative"
    )

    events = df[[date_col, location_col]].drop_duplicates().copy()

    def extract_event_label(loc):
        return loc.split("/")[0].strip()

    events["Event"] = events[location_col].apply(extract_event_label)

    events = events[events[date_col].dt.date <= today]

    cum_pos["__date_only"] = pd.to_datetime(cum_pos[date_col]).dt.normalize()
    events["__date_only"] = events[date_col].dt.normalize()

    merged = cum_pos.merge(
        events[["__date_only", "Event"]], on="__date_only", how="inner"
    )

    order = latest_totals[positive_names].sort_values(ascending=False).index.tolist()

    events_order = events.sort_values(by=date_col)["Event"].tolist()

    chart = alt.Chart(merged).mark_line().encode(
        x=alt.X("Event:N", sort=events_order, title="Evento"),
        y=alt.Y("Cumulative:Q", title="Puntos acumulados"),
        color=alt.Color("Name:N", sort=order),
        tooltip=["Event", "Name", "Cumulative"]
    ).properties(height=350)

    st.altair_chart(chart, use_container_width=True)

# -------- Standings --------
st.markdown("## Standings actuales")

latest = cum.iloc[-1].sort_values(ascending=False)

names = list(latest.index)
points = list(latest.values)

total = len(names)
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

html_cols = ['<div style="display:flex;gap:40px">']

for chunk in chunks:

    items = []

    for rank, nm, pts in chunk:

        pts_text = str(int(pts)) if float(pts).is_integer() else str(round(pts,2))

        items.append(
            f"<div>{rank}. {html.escape(nm)} — {pts_text}</div>"
        )

    html_cols.append("<div>" + "".join(items) + "</div>")

html_cols.append("</div>")

st.markdown("\n".join(html_cols), unsafe_allow_html=True)

# -------- Historial --------
st.markdown("## Historial completo")

def df_to_html_table_with_location(df_in):

    df_copy = df_in.copy()
    df_copy[date_col] = df_copy[date_col].dt.strftime("%Y-%m-%d")

    cols = [date_col, location_col] + score_cols

    thead = "<thead><tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr></thead>"

    rows_html = []

    for _, row in df_copy.iterrows():

        cells = []

        cells.append(f"<td>{row[date_col]}</td>")
        cells.append(f"<td>{row[location_col]}</td>")

        for sc in score_cols:

            try:
                v = float(row[sc])
                cell_text = str(int(v)) if v.is_integer() else str(round(v,2))
            except:
                cell_text = row[sc]

            cells.append(f"<td>{cell_text}</td>")

        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    tbody = "<tbody>" + "\n".join(rows_html) + "</tbody>"

    table_html = f"<table>{thead}{tbody}</table>"

    return table_html

st.markdown(df_to_html_table_with_location(df), unsafe_allow_html=True)
