# -------- Chart (first) --------
st.markdown("<h2>Puntaje a lo largo del tiempo</h2>", unsafe_allow_html=True)

if not cum.empty and cum.shape[1] > 0:
    # Determinar "hoy" en la zona horaria del usuario, con fallback si pytz no está disponible
    try:
        import pytz
        today_ts = pd.Timestamp.now(tz=pytz.timezone("America/Argentina/Buenos_Aires")).normalize()
    except Exception:
        today_ts = pd.Timestamp.now().normalize()

    today_date = today_ts.date()

    # Filtrar columnas (participantes) que tengan algún punto en el total final (>0)
    latest_totals = cum.iloc[-1]  # últimos acumulados por participante
    positive_names = latest_totals[latest_totals > 0].index.tolist()

    if len(positive_names) == 0:
        st.info("No hay participantes con puntos (todos tienen 0). El gráfico no se mostrará.")
    else:
        # Construir DataFrame 'long' solo con participantes positivos
        cum_pos = cum[positive_names].reset_index().melt(id_vars=[date_col], var_name="Name", value_name="Cumulative")
        cum_pos[date_col] = pd.to_datetime(cum_pos[date_col])

        # Preparar tabla de eventos (una fila por evento/fecha) para etiquetas
        events = df[[date_col, location_col]].drop_duplicates(subset=[date_col]).sort_values(by=date_col).copy()
        events[date_col] = pd.to_datetime(events[date_col], errors='coerce')

        # Extraer etiqueta del lugar: parte antes de '/' (ej: "Australia / Albert Park Circuit" -> "Australia")
        def extract_event_label(loc):
            if not isinstance(loc, str) or loc.strip() == "":
                return ""
            # tomar la parte antes del '/', si no existe tomar toda la cadena
            part = loc.split("/")[0]
            # además eliminar cualquier sufijo con '-' y espacios sobrantes
            part = part.split("-")[0].strip()
            return part

        events["Event"] = events[location_col].astype(str).apply(extract_event_label)

        # Filtrar eventos hasta hoy (por fecha)
        events = events[events[date_col].notna()].copy()
        events = events[events[date_col].dt.date <= today_date]

        if events.empty:
            st.info("No hay eventos hasta la fecha actual para mostrar en el gráfico.")
        else:
            # Merge cum_pos con events por la fecha para obtener la etiqueta "Event"
            # Asegurarnos de que las fechas en cum_pos coincidan en tipo con events
            cum_pos = cum_pos[cum_pos[date_col].notna()].copy()
            # convertir a fecha (sin hora) para merge seguro
            cum_pos["__date_only"] = cum_pos[date_col].dt.normalize()
            events["__date_only"] = events[date_col].dt.normalize()

            # Hacer merge (left join) para traer la etiqueta del evento a cada fila de cum_pos
            cum_pos = cum_pos.merge(events[[ "__date_only", "Event", location_col]], on="__date_only", how="inner")
            # Si quedó vacío, avisar
            if cum_pos.empty:
                st.info("Después de filtrar por fecha y participantes con puntos no quedan filas para graficar.")
            else:
                # Orden de eventos (etiquetas) por fecha para que Altair los muestre en ese orden
                events_order = events.sort_values(by=date_col)["Event"].tolist()
                # En algunos casos puede haber etiquetas repetidas; mantener el orden preservando primera aparición:
                seen = set()
                ordered_events = [x for x in events_order if not (x in seen or seen.add(x))]

                # Orden de participantes por total final descendente (consistencia colores/leyenda)
                order = latest_totals[positive_names].sort_values(ascending=False).index.tolist()
                color_scale = alt.Color("Name:N", sort=order, legend=alt.Legend(title="Participante"))

                # Usar 'Event' (categorical) en el eje X, con orden explícito
                chart = alt.Chart(cum_pos).mark_line(interpolate="monotone").encode(
                    x=alt.X("Event:N", title="Evento (ubicación)", sort=ordered_events, axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("Cumulative:Q", title="Puntos acumulados"),
                    color=color_scale,
                    tooltip=[alt.Tooltip("__date_only:T", title="Fecha"), "Event:N", "Name:N", alt.Tooltip("Cumulative:Q", format=".2f")]
                ).properties(height=360)

                st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
                st.altair_chart(chart, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("No hay datos de puntaje suficientes para generar el gráfico.")
