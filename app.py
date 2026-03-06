import streamlit as st
import pandas as pd
import altair as alt
from io import StringIO

st.set_page_config(page_title="Score Tracker", layout="wide")

st.title("Score Tracker")

# ---------- Cargar CSV (desde repo publicado) ----------
@st.cache_data
def load_from_repo(path="data/scores.csv"):
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        return None

df = load_from_repo()

# ---------- Sidebar: subir CSV para probar localmente ----------
st.sidebar.header("Actualizar datos (prueba)")
uploaded = st.sidebar.file_uploader("Subir un CSV nuevo (sustituye temporalmente)", type=["csv"])
if uploaded is not None:
    content = uploaded.read().decode("utf-8")
    df = pd.read_csv(StringIO(content))
    st.sidebar.success("CSV cargado en memoria (no persiste en el repo).")

# ---------- Validaciones básicas ----------
if df is None:
    st.error("No se pudo leer data/scores.csv. Verificá que exista en el repo.")
    st.stop()

# Esperamos formato: primera columna 'Date', siguientes columnas nombres
df.columns = df.columns.astype(str)
date_col = df.columns[0]
df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
df = df.sort_values(by=date_col)

# Mostrar historial completo
st.header("Historial completo")
st.dataframe(df, use_container_width=True)

# ---------- Calcular puntajes acumulados ----------
# Asumimos que cada celda (después de Date) es 0/1 o número de puntos por evento
scores = df.set_index(date_col).fillna(0).astype(float)
cum = scores.cumsum()

# Mostrar tabla de standings actuales (última fila acumulada)
st.header("Standings actuales")
latest = cum.iloc[-1].sort_values(ascending=False).reset_index()
latest.columns = ["Name", "Total Points"]
st.table(latest)

# ---------- Gráfico: puntaje a lo largo del tiempo ----------
st.header("Puntaje a lo largo del tiempo")
# Transformar para Altair
cum_reset = cum.reset_index().melt(id_vars=[date_col], var_name="Name", value_name="Cumulative")
chart = alt.Chart(cum_reset).mark_line().encode(
    x=date_col,
    y="Cumulative",
    color="Name",
    tooltip=[date_col, "Name", "Cumulative"]
).interactive()

st.altair_chart(chart, use_container_width=True)

# ---------- Opciones para persistencia (explicación) ----------
st.markdown("### Notas sobre persistencia")
st.markdown(
"""
- **Subir un CSV aquí**: reemplaza los datos *en memoria* para la sesión actual, **no** modifica el archivo en tu repo.
- **Para que los cambios persistan en la web** hay 2 enfoques comunes:
  1. **Editar y commitear `data/scores.csv` en GitHub** (push). Streamlit volverá a desplegar si usás Streamlit Cloud conectado al repo.
  2. **Usar una fuente externa editable** (Google Sheets, Supabase, Firebase, S3). La app puede leer/escribir ahí y los cambios son persistentes sin commits.
- Si querés, puedo añadir el código para guardar cambios directo en GitHub usando la API (requiere un token) o para integrar Google Sheets.
"""
)
