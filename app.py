import os
import csv
from io import StringIO
import html
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="F1 tabla de posiciones", layout="wide")

# -------- CSV robusto --------
def try_read_csv_from_text(raw_text):
    if not raw_text:
        return None
    try:
        sample = raw_text[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        sep = dialect.delimiter
    except Exception:
        header_line = raw_text.splitlines()[0]
        counts = {",": header_line.count(","), ";": header_line.count(";"), "\t": header_line.count("\t"), "|": header_line.count("|")}
        sep = max(counts, key=counts.get)
    for s in [sep, ",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(StringIO(raw_text), sep=s)
            if df.shape[1] > 1:
                return df
        except:
            continue
    return None

def try_read_csv(path):
    if not os.path.exists(path):
        return None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                raw = f.read()
            return try_read_csv_from_text(raw)
        except:
            continue
    return None

# -------- Inject CSS --------
def inject_css(file_name="style.css"):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

inject_css()

# -------- Layout --------
st.markdown('<div class="top-banner"><div class="container"><h1>F1 tabla de posiciones</h1></div></div>', unsafe_allow_html=True)
st.markdown('<div class="container">', unsafe_allow_html=True)

DATA_PATH = "data/scores.csv"
df = try_read_csv(DATA_PATH)

if df is None:
    st.error("No se pudo leer data/scores.csv")
    st.stop()

df.columns = df.columns.astype(str)
date_col = df.columns[0]
df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
df = df.sort_values(by=date_col)

score_cols = df.columns[1:]

for c in score_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

scores = df.set_index(date_col)[score_cols]
cum = scores.cumsum()

# -------- Chart --------
st.markdown("<h2>Puntaje a lo largo del tiempo</h2>", unsafe_allow_html=True)

cum_reset = cum.reset_index().melt(id_vars=[date_col], var_name="Name", value_name="Cumulative")

chart = alt.Chart(cum_reset).mark_line().encode(
    x=date_col,
    y="Cumulative",
    color="Name",
    tooltip=[date_col, "Name", "Cumulative"]
).properties(height=360)

st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
st.altair_chart(chart, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# -------- Standings --------
st.markdown("<h2>Standings actuales</h2>", unsafe_allow_html=True)

latest = cum.iloc[-1].sort_values(ascending=False)

items = []
for i, (name, pts) in enumerate(latest.items(), start=1):
    items.append(
        f'<li class="standings-item"><div class="standings-name">{html.escape(str(name))}</div><div class="standings-score">{int(pts)}</div></li>'
    )

st.markdown('<ul class="standings-list">' + "\n".join(items) + "</ul>", unsafe_allow_html=True)

# -------- Historial --------
st.markdown("<h2>Historial completo</h2>", unsafe_allow_html=True)

def build_table(df):
    df_copy = df.copy()
    df_copy[date_col] = df_copy[date_col].dt.strftime("%Y-%m-%d")
    cols = df_copy.columns.tolist()
    thead = "<thead><tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr></thead>"
    rows = []
    for _, row in df_copy.iterrows():
        cells = []
        for i, col in enumerate(cols):
            if i == 0:
                cells.append(f"<td>{row[col]}</td>")
            else:
                cells.append(f'<td class="numeric">{int(row[col])}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    tbody = "<tbody>" + "\n".join(rows) + "</tbody>"
    return f'<div class="table-wrapper"><table>{thead}{tbody}</table></div>'

st.markdown(build_table(df), unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
