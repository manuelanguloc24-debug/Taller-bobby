import datetime
import json
import re
import requests
import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="AutoControl Pro | Gestión de Taller",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONEXIÓN A GOOGLE SHEETS ---
SHEET_ID = "1oZR5yx18Buk-zZyu3u60AGpc7LozijGZa2yrpOOx364"
WEBHOOK_URL = "PEGA_AQUI_TU_URL_DE_APPS_SCRIPT_EXEC"

ESTADOS = [
    "Diagnóstico",
    "Esperando aprobación",
    "Esperando repuestos",
    "En reparación",
    "Listo para entrega",
    "Entregado"
]

# --- ESTILO VISUAL PREMIUM (DARK & GOLD) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .stApp {
        background-color: #0B0D10;
        color: #F3F4F6;
    }

    .kpi-card {
        background: linear-gradient(145deg, #1E1912, #121418 75%);
        border-radius: 14px;
        padding: 20px 22px;
        border: 1px solid #6A532D;
        border-top: 3px solid #E5B95D;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
        margin-bottom: 12px;
    }
    .kpi-title {
        color: #F4D99E;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-bottom: 6px;
    }
    .kpi-value {
        color: #FFFFFF;
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 4px;
        font-variant-numeric: tabular-nums;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #ACB6C6;
    }
    .kpi-pos { color: #4ADE80; font-weight: 600; }
    .kpi-neg { color: #F87171; font-weight: 600; }

    div[data-testid="stForm"], div[data-testid="stExpander"] details {
        background-color: #121418 !important;
        border: 1px solid #2D333F !important;
        border-radius: 14px !important;
    }

    .stButton > button {
        background: linear-gradient(90deg, #D4A349, #E5B95D) !important;
        color: #0B0D10 !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 8px 16px !important;
    }
    .stButton > button:hover {
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE CONEXIÓN ---
@st.cache_data(ttl=15)
def cargar_tabla(nombre_pestana):
    pestana_url = nombre_pestana.replace(" ", "%20")
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={pestana_url}"
    df = pd.read_csv(url)
    df.columns = df.columns.astype(str).str.strip().str.lower()
    return df

def limpiar_numero(columna):
    return pd.to_numeric(
        columna.astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False),
        errors='coerce'
    ).fillna(0.0)

def enviar_webhook(payload):
    try:
        headers = {"Content-Type": "application/json"}
        resp = requests.post(
            WEBHOOK_URL,
            data=json.dumps(payload),
            headers=headers,
            timeout=15,
            allow_redirects=True
        )
        res_json = resp.json()
        return res_json.get("status") == "success", res_json.get("message", "")
    except Exception as e:
        return False, str(e)

# --- BARRA LATERAL ---
st.sidebar.markdown("## 🔧 **AutoControl Pro**")
st.sidebar.caption("Sistema de Gestión Automotriz")

st.sidebar.link_button(
    "📊 Abrir Base en Google Sheets",
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
    use_container_width=True
)

if st.sidebar.button("🔄 Sincronizar Datos", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# --- NAVEGACIÓN PRINCIPAL ---
tab_resumen, tab_ordenes, tab_registrar = st.tabs([
    "📊 Resumen Ejecutivo",
    "🚗 Órdenes en Taller",
    "📝 Registrar Operación"
])

# --- CARGA DE DATOS ---
try:
    ordenes_df = cargar_tabla("Ordenes")
    movimientos_df = cargar_tabla("Movimientos")
    costos_fijos_df = cargar_tabla("Costos_Fijos")

    # Preparar datos de Órdenes
    if not ordenes_df.empty:
        ordenes_df['precio_acordado'] = limpiar_numero(ordenes_df['precio_acordado'])
        ordenes_df['id_orden'] = ordenes_df['id_orden'].astype(str).str.strip()
        ordenes_df['estado'] = ordenes_df['estado'].fillna("Diagnóstico").astype(str).str.strip()
        ordenes_df['fecha_ingreso_dt'] = pd.to_datetime(ordenes_df['fecha_ingreso'], errors='coerce')
        ordenes_df['fecha_estado_dt'] = pd.to_datetime(ordenes_df['fecha_estado'], errors='coerce').fillna(ordenes_df['fecha_ingreso_dt'])
        ordenes_df['fecha_entrega_dt'] = pd.to_datetime(ordenes_df['fecha_entrega'], errors='coerce')
    else:
        ordenes_df = pd.DataFrame(columns=[
            'id_orden', 'fecha_ingreso', 'placa_vehiculo', 'cliente', 'servicio',
            'tecnico', 'precio_acordado', 'estado', 'fecha_estado', 'fecha_entrega'
        ])

    # Preparar datos de Movimientos (Cobros y Gastos)
    if not movimientos_df.empty:
        movimientos_df['monto'] = limpiar_numero(movimientos_df['monto'])
        movimientos_df['id_orden'] = movimientos_df['id_orden'].astype(str).str.strip()
        movimientos_df['tipo'] = movimientos_df['tipo'].astype(str).str.strip()
        movimientos_df['fecha_dt'] = pd.to_datetime(movimientos_df['fecha'], errors='coerce')
        
        cobros_por_orden = movimientos_df[movimientos_df['tipo'].str.lower() == 'cobro'].groupby('id_orden')['monto'].sum()
        gastos_por_orden = movimientos_df[movimientos_df['tipo'].str.lower() == 'gasto'].groupby('id_orden')['monto'].sum()
    else:
        cobros_por_orden = pd.Series(dtype=float)
        gastos_por_orden = pd.Series(dtype=float)

    if not ordenes_df.empty:
        ordenes_df['cobrado'] = ordenes_df['id_orden'].map(cobros_por_orden).fillna(0.0)
        ordenes_df['gastos_directos'] = ordenes_df['id_orden'].map(gastos_por_orden).fillna(0.0)
        ordenes_df['saldo_pendiente'] = (ordenes_df['precio_acordado'] - ordenes_df['cobrado']).clip(lower=0.0)
        ordenes_df['ganancia_orden'] = ordenes_df['precio_acordado'] - ordenes_df['gastos_directos']

    costos_fijos_totales = limpiar_numero(costos_fijos_df['monto_mensual']).sum() if not costos_fijos_df.empty else 0.0

except Exception as e:
    st.error(f"⚠️ Error al leer Google Sheets. Verifica que la hoja esté compartida como 'Cualquier persona con el enlace (Lector)': {e}")
    st.stop()

# ==============================================================================
# PESTAÑA 1: RESUMEN EJECUTIVO
# ==============================================================================
with tab_resumen:
    hoy = pd.Timestamp.today().normalize()
    mes_actual = hoy.strftime('%Y-%m')
    
    meses_lista = sorted(list(set([mes_actual] + (ordenes_df['fecha_ingreso_dt'].dropna().dt.strftime('%Y-%m').tolist() if not ordenes_df.empty else []))), reverse=True)
    mes_consulta = st.sidebar.selectbox("Periodo Financiero:", meses_lista)

    # Filtrar entregados del mes seleccionado
    if not ordenes_df.empty:
        entregados_mes = ordenes_df[
            (ordenes_df['estado'] == 'Entregado') &
            (ordenes_df['fecha_entrega_dt'].dt.strftime('%Y-%m') == mes_consulta)
        ]
        ingresos_entregados = entregados_mes['precio_acordado'].sum()
        costos_entregados = entregados_mes['gastos_directos'].sum()
        ganancia_neta_trabajos = ingresos_entregados - costos_entregados
        ticket_promedio = ingresos_entregados / len(entregados_mes) if len(entregados_mes) > 0 else 0.0
        saldo_por_cobrar_total = ordenes_df['saldo_pendiente'].sum()
    else:
        ingresos_entregados = costos_entregados = ganancia_neta_trabajos = ticket_promedio = saldo_por_cobrar_total = 0.0
        entregados_mes = pd.DataFrame()

    # Cobros reales ingresados a caja en el mes
    if not movimientos_df.empty:
        cobrado_mes = movimientos_df[
            (movimientos_df['tipo'].str.lower() == 'cobro') &
            (movimientos_df['fecha_dt'].dt.strftime('%Y-%m') == mes_consulta)
        ]['monto'].sum()
    else:
        cobrado_mes = 0.0

    # --- TARJETAS KPI ---
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Trabajos Entregados ({mes_consulta})</div>
            <div class="kpi-value">${ingresos_entregados:,.2f}</div>
            <div class="kpi-sub">{len(entregados_mes)} vehículos entregados</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Cobrado en Caja ({mes_consulta})</div>
            <div class="kpi-value">${cobrado_mes:,.2f}</div>
            <div class="kpi-sub kpi-pos">Flujo efectivo recibido</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Cartera por Cobrar Total</div>
            <div class="kpi-value">${saldo_por_cobrar_total:,.2f}</div>
            <div class="kpi-sub kpi-neg">Saldos pendientes en órdenes</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Ganancia Bruta Entregados</div>
            <div class="kpi-value">${ganancia_neta_trabajos:,.2f}</div>
            <div class="kpi-sub">Ticket promedio: ${ticket_promedio:,.2f}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- GRÁFICOS Y ALERTAS ---
    col_g1, col_g2 = st.columns([1.1, 1])

    with col_g1:
        st.markdown("#### 🎯 Punto de Equilibrio Mensual")
        if not ordenes_df.empty and ordenes_df['precio_acordado'].sum() > 0:
            total_ventas_hist = ordenes_df['precio_acordado'].sum()
            total_costos_hist = ordenes_df['gastos_directos'].sum()
            margen_pct = max(0.1, (total_ventas_hist - total_costos_hist) / total_ventas_hist)
            meta_ventas = costos_fijos_totales / margen_pct if costos_fijos_totales > 0 else 0.0
        else:
            meta_ventas = costos_fijos_totales

        faltante_meta = max(0.0, meta_ventas - ingresos_entregados)
        
        if meta_ventas > 0:
            df_eq = pd.DataFrame({
                "Estado": ["Facturado Entregado", "Faltante para Equilibrio"],
                "Monto": [ingresos_entregados, faltante_meta]
            })
            fig_pie = px.pie(
                df_eq, values="Monto", names="Estado", hole=0.62,
                color="Estado",
                color_discrete_map={"Facturado Entregado": "#E5B95D", "Faltante para Equilibrio": "#2D333F"}
            )
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#F3F4F6", margin=dict(t=20, b=20, l=10, r=10), height=280
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            st.caption(f"Costos Fijos: **${costos_fijos_totales:,.2f}** · Meta estimada de facturación: **${meta_ventas:,.2f}**")
        else:
            st.info("Agrega tus costos fijos en la pestaña 'Costos_Fijos' del Google Sheet para visualizar el punto de equilibrio.")

    with col_g2:
        st.markdown("#### ⚠️ Alertas: Vehículos Estancados en Taller")
        dias_alerta = st.number_input("Alertar si lleva más de (días) en la misma etapa:", min_value=1, value=4)
        
        if not ordenes_df.empty:
            activas = ordenes_df[ordenes_df['estado'] != 'Entregado'].copy()
            if not activas.empty:
                activas['dias_en_etapa'] = (hoy - activas['fecha_estado_dt']).dt.days.fillna(0).astype(int)
                estancadas = activas[activas['dias_en_etapa'] >= dias_alerta].sort_values(by='dias_en_etapa', ascending=False)
                
                if not estancadas.empty:
                    for _, r in estancadas.iterrows():
                        st.error(f"🚨 **{r['id_orden']} · {r['placa_vehiculo']}** ({r['cliente']}) — Lleva **{r['dias_en_etapa']} días** en *{r['estado']}*")
                else:
                    st.success("✅ Flujo saludable: ningún vehículo supera el límite de días en su etapa actual.")
            else:
                st.info("No hay vehículos activos en taller.")

# ==============================================================================
# PESTAÑA 2: ÓRDENES EN TALLER (TABLERO DE ESTADOS)
# ==============================================================================
with tab_ordenes:
    st.markdown("### 🚗 Control de Vehículos y Órdenes de Trabajo")
    
    busqueda = st.text_input("🔍 Buscar por placa, cliente, servicio o número de orden:", placeholder="Ej. P123-456 o Carlos").strip().lower()
    
    if not ordenes_df.empty:
        if busqueda:
            mask = (
                ordenes_df['id_orden'].str.lower().str.contains(busqueda, na=False) |
                ordenes_df['placa_vehiculo'].astype(str).str.lower().str.contains(busqueda, na=False) |
                ordenes_df['cliente'].astype(str).str.lower().str.contains(busqueda, na=False) |
                ordenes_df['servicio'].astype(str).str.lower().str.contains(busqueda, na=False)
            )
            df_filtrado = ordenes_df[mask]
        else:
            df_filtrado = ordenes_df

        activos_df = df_filtrado[df_filtrado['estado'] != 'Entregado']

        sub_tablero, sub_lista, sub_historial = st.tabs([
            f"🛠️ Tablero por Etapa ({len(activos_df)})",
            f"📋 Lista General ({len(df_filtrado)})",
            "💵 Historial de Cobros y Repuestos"
        ])

        with sub_tablero:
            if activos_df.empty:
                st.info("No hay órdenes activas en el taller.")
            else:
                for estado_actual in ESTADOS[:-1]:
                    grupo = activos_df[activos_df['estado'] == estado_actual]
                    with st.expander(f"📌 {estado_actual} ({len(grupo)} vehículos)", expanded=bool(len(grupo) > 0)):
                        for _, row in grupo.iterrows():
                            with st.container(border=True):
                                c1, c2 = st.columns([2.2, 1])
                                with c1:
                                    st.markdown(f"**{row['id_orden']} · {row['placa_vehiculo']}** — *{row['servicio']}*")
                                    st.caption(f"👤 Cliente: {row['cliente']} | 👨‍🔧 Técnico: {row['tecnico'] or 'Sin asignar'} | 📅 Ingreso: {row['fecha_ingreso']}")
                                    st.write(f"💰 Precio: **${row['precio_acordado']:,.2f}** | Cobrado: **${row['cobrado']:,.2f}** | Saldo: **${row['saldo_pendiente']:,.2f}** | Repuestos/Gastos: **${row['gastos_directos']:,.2f}**")
                                with c2:
                                    nuevo_est = st.selectbox(
                                        "Mover a etapa:",
                                        ESTADOS,
                                        index=ESTADOS.index(estado_actual),
                                        key=f"sel_{row['id_orden']}"
                                    )
                                    if st.button("Actualizar", key=f"btn_{row['id_orden']}", use_container_width=True):
                                        if nuevo_est != estado_actual:
                                            ok, msg = enviar_webhook({
                                                "accion": "cambiar_estado",
                                                "pestana": "Ordenes",
                                                "id_orden": row['id_orden'],
                                                "estado": nuevo_est,
                                                "fecha": str(datetime.date.today())
                                            })
                                            if ok:
                                                st.success(f"✅ {msg}")
                                                st.cache_data.clear()
                                                st.rerun()
                                            else:
                                                st.error(f"Error: {msg}")

        with sub_lista:
            if not df_filtrado.empty:
                vista = df_filtrado[[
                    'id_orden', 'fecha_ingreso', 'placa_vehiculo', 'cliente', 'servicio',
                    'estado', 'precio_acordado', 'cobrado', 'saldo_pendiente', 'gastos_directos', 'ganancia_orden'
                ]].rename(columns={
                    'id_orden': 'Orden', 'fecha_ingreso': 'Ingreso', 'placa_vehiculo': 'Vehículo',
                    'cliente': 'Cliente', 'servicio': 'Trabajo', 'estado': 'Estado',
                    'precio_acordado': 'Precio ($)', 'cobrado': 'Cobrado ($)',
                    'saldo_pendiente': 'Pendiente ($)', 'gastos_directos': 'Gastos ($)', 'ganancia_orden': 'Margen ($)'
                })
                st.dataframe(vista, use_container_width=True, hide_index=True)

        with sub_historial:
            if not movimientos_df.empty:
                st.dataframe(
                    movimientos_df[['fecha', 'id_orden', 'tipo', 'concepto', 'monto']].sort_values(by='fecha', ascending=False),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Aún no se han registrado cobros ni gastos de repuestos.")
    else:
        st.info("No hay órdenes registradas todavía. Ve a la pestaña 'Registrar Operación' para crear la primera.")

# ==============================================================================
# PESTAÑA 3: REGISTRAR OPERACIÓN (NUEVA ORDEN O MOVIMIENTO)
# ==============================================================================
with tab_registrar:
    st.markdown("### 📝 Registro de Operaciones del Taller")
    col_izq, col_der = st.columns(2)

    # --- FORMULARIO 1: NUEVA ORDEN DE TRABAJO (CORRELATIVO REUTILIZABLE) ---
    with col_izq:
        st.markdown("#### 🚘 Abrir Nueva Orden de Trabajo")
        
        siguiente_ot = "OT-001"
        if not ordenes_df.empty:
            nums = []
            for item in ordenes_df['id_orden'].dropna().astype(str):
                m = re.search(r'OT-(\d+)', item, re.IGNORECASE)
                if m:
                    nums.append(int(m.group(1)))
            if nums:
                siguiente_ot = f"OT-{max(nums) + 1:03d}"

        with st.form("form_nueva_orden", clear_on_submit=True):
            c_ot1, c_ot2 = st.columns(2)
            with c_ot1:
                id_nueva_ot = st.text_input("N° Orden Correlativo", value=siguiente_ot)
            with c_ot2:
                fecha_in = st.date_input("Fecha de Ingreso", datetime.date.today())

            placa = st.text_input("Placa / Vehículo", placeholder="Ej. P456-789 Toyota Hilux").strip()
            cliente_nombre = st.text_input("Nombre del Cliente", placeholder="Ej. Carlos Mendoza").strip()
            servicio_desc = st.text_input("Trabajo / Servicio Solicitado", placeholder="Ej. Cambio de frenos y rectificación").strip()
            
            c_ot3, c_ot4 = st.columns(2)
            with c_ot3:
                tecnico_nombre = st.text_input("Mecánico Asignado", placeholder="Ej. Luis").strip()
            with c_ot4:
                precio_acordado = st.number_input("Presupuesto Acordado ($)", min_value=0.0, step=5.0, format="%.2f")

            if st.form_submit_button("💾 Crear Orden de Trabajo", use_container_width=True):
                if placa and servicio_desc and precio_acordado > 0:
                    fila_orden = [
                        id_nueva_ot, str(fecha_in), placa, cliente_nombre or "Cliente General",
                        servicio_desc, tecnico_nombre or "Por asignar", float(precio_acordado),
                        "Diagnóstico", str(fecha_in), ""
                    ]
                    ok, msg = enviar_webhook({"accion": "agregar", "pestana": "Ordenes", "fila": fila_orden})
                    if ok:
                        st.success(f"✅ Orden **{id_nueva_ot}** creada exitosamente.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Error al guardar: {msg}")
                else:
                    st.error("Completa al menos la placa, el servicio y un precio mayor a $0.")

    # --- FORMULARIO 2: REGISTRAR ABONO O GASTO DE REPUESTOS ---
    with col_der:
        st.markdown("#### 💵 Registrar Cobro o Gasto de Repuestos")
        if not ordenes_df.empty:
            opciones_ot = {
                f"{r['id_orden']} · {r['placa_vehiculo']} ({r['cliente']}) — Saldo: ${r['saldo_pendiente']:,.2f}": r['id_orden']
                for _, r in ordenes_df.iterrows()
            }
            with st.form("form_movimiento", clear_on_submit=True):
                ot_seleccionada_label = st.selectbox("Seleccionar Orden de Trabajo:", list(opciones_ot.keys()))
                
                c_m1, c_m2 = st.columns(2)
                with c_m1:
                    tipo_mov = st.radio("Tipo de Registro:", ["Cobro", "Gasto"], horizontal=True)
                with c_m2:
                    fecha_mov = st.date_input("Fecha", datetime.date.today())

                concepto_mov = st.text_input("Detalle / Concepto", placeholder="Ej. Abono inicial 50% o Compra de pastillas de freno").strip()
                monto_mov = st.number_input("Monto ($)", min_value=0.01, step=1.0, format="%.2f")

                if st.form_submit_button("💾 Registrar Movimiento", use_container_width=True):
                    if concepto_mov:
                        id_ot_real = opciones_ot[ot_seleccionada_label]
                        fila_mov = [str(fecha_mov), id_ot_real, tipo_mov, concepto_mov, float(monto_mov)]
                        ok, msg = enviar_webhook({"accion": "agregar", "pestana": "Movimientos", "fila": fila_mov})
                        if ok:
                            st.success(f"✅ {tipo_mov} de **${monto_mov:,.2f}** asociado a **{id_ot_real}**.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Error: {msg}")
                    else:
                        st.error("Escribe el detalle del cobro o repuesto.")
        else:
            st.info("Crea primero una orden de trabajo para poder asociarle cobros o gastos de repuestos.")

    # --- OPCIÓN DE BORRADO RÁPIDO POR ERROR ---
    st.markdown("---")
    with st.expander("🗑️ Corregir: Eliminar última orden o último movimiento registrado"):
        c_del1, c_del2 = st.columns(2)
        with c_del1:
            if not ordenes_df.empty:
                ultima_fila_ot = len(ordenes_df) + 1
                ultima_ot_id = ordenes_df.iloc[-1]['id_orden']
                if st.button(f"🗑️ Eliminar Última Orden ({ultima_ot_id})", use_container_width=True):
                    ok, msg = enviar_webhook({"accion": "borrar", "pestana": "Ordenes", "fila_index": ultima_fila_ot})
                    if ok:
                        st.warning(f"Orden {ultima_ot_id} eliminada. El correlativo volverá a usar ese número.")
                        st.cache_data.clear()
                        st.rerun()
        with c_del2:
            if not movimientos_df.empty:
                ultima_fila_mov = len(movimientos_df) + 1
                if st.button("🗑️ Eliminar Último Cobro/Gasto", use_container_width=True):
                    ok, msg = enviar_webhook({"accion": "borrar", "pestana": "Movimientos", "fila_index": ultima_fila_mov})
                    if ok:
                        st.warning("Último movimiento eliminado.")
                        st.cache_data.clear()
                        st.rerun()
