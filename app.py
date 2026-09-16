"""
FLUJO DE CAJA & DASHBOARD — Aplicación Multi-Cliente
=====================================================
Streamlit + Supabase (PostgreSQL)
Autor: Darwin / contabilidadenlinea15@gmail.com
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import date, datetime, timedelta
import calendar
import json

# ──────────────────────────────────────────────
# 1. CONFIGURACIÓN Y CONEXIÓN A SUPABASE
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="Flujo de Caja — Dashboard Multi-Cliente",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def init_supabase():
    """Conexión única a Supabase usando los secrets de Streamlit."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = init_supabase()

# ──────────────────────────────────────────────
# 2. FUNCIONES AUXILIARES DE BASE DE DATOS
# ──────────────────────────────────────────────


def cargar_empresas():
    """Devuelve lista de empresas registradas."""
    resp = supabase.table("empresas").select("*").order("nombre").execute()
    return resp.data


def crear_empresa(nombre, rif, direccion):
    """Inserta una empresa nueva."""
    supabase.table("empresas").insert(
        {"nombre": nombre, "rif": rif, "direccion": direccion}
    ).execute()


def cargar_bancos(empresa_id):
    resp = (
        supabase.table("bancos")
        .select("*")
        .eq("empresa_id", empresa_id)
        .order("nombre")
        .execute()
    )
    return resp.data


def crear_banco(empresa_id, nombre, tipo):
    supabase.table("bancos").insert(
        {"empresa_id": empresa_id, "nombre": nombre, "tipo": tipo}
    ).execute()


def cargar_categorias():
    resp = (
        supabase.table("categorias")
        .select("*")
        .order("partida_fc")
        .execute()
    )
    return resp.data


def cargar_tasas(empresa_id, mes=None, anio=None):
    q = supabase.table("tasas_cambio").select("*").eq("empresa_id", empresa_id)
    if mes and anio:
        inicio = f"{anio}-{mes:02d}-01"
        fin_dia = calendar.monthrange(anio, mes)[1]
        fin = f"{anio}-{mes:02d}-{fin_dia:02d}"
        q = q.gte("fecha", inicio).lte("fecha", fin)
    resp = q.order("fecha", desc=True).execute()
    return resp.data


def guardar_tasa(empresa_id, fecha, bcv, euro, binance):
    supabase.table("tasas_cambio").upsert(
        {
            "empresa_id": empresa_id,
            "fecha": fecha,
            "tasa_bcv": bcv,
            "tasa_euro": euro,
            "tasa_binance": binance,
        },
        on_conflict="empresa_id,fecha",
    ).execute()


def cargar_movimientos(empresa_id, filtros=None):
    q = (
        supabase.table("movimientos")
        .select("*, bancos(nombre), categorias(subclasificacion, clasificacion, partida_fc)")
        .eq("empresa_id", empresa_id)
    )
    if filtros:
        if filtros.get("mes") and filtros.get("anio"):
            m, a = filtros["mes"], filtros["anio"]
            inicio = f"{a}-{m:02d}-01"
            fin_dia = calendar.monthrange(a, m)[1]
            fin = f"{a}-{m:02d}-{fin_dia:02d}"
            q = q.gte("fecha", inicio).lte("fecha", fin)
        if filtros.get("banco_id"):
            q = q.eq("banco_id", filtros["banco_id"])
        if filtros.get("partida_fc"):
            q = q.eq("partida_fc", filtros["partida_fc"])
    resp = q.order("fecha", desc=True).limit(1000).execute()
    return resp.data


def guardar_movimiento(data):
    supabase.table("movimientos").insert(data).execute()


def actualizar_movimiento(mov_id, data):
    supabase.table("movimientos").update(data).eq("id", mov_id).execute()


def eliminar_movimiento(mov_id):
    supabase.table("movimientos").delete().eq("id", mov_id).execute()


# ──────────────────────────────────────────────
# 3. ESTILOS PERSONALIZADOS
# ──────────────────────────────────────────────

st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .metric-card h3 { font-size: 0.85rem; opacity: 0.8; margin-bottom: 4px; }
    .metric-card h1 { font-size: 1.6rem; margin: 0; }
    .metric-positive { border-left: 4px solid #00d4aa; }
    .metric-negative { border-left: 4px solid #ff6b6b; }
    .metric-neutral  { border-left: 4px solid #4ecdc4; }
    .metric-warning  { border-left: 4px solid #ffa726; }
    </style>
    """,
    unsafe_allow_html=True,
)


def tarjeta_metrica(titulo, valor, clase="neutral"):
    return f"""
    <div class="metric-card metric-{clase}">
        <h3>{titulo}</h3>
        <h1>{valor}</h1>
    </div>
    """


# ──────────────────────────────────────────────
# 4. SIDEBAR — SELECTOR DE EMPRESA + NAVEGACIÓN
# ──────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/cash-in-hand.png", width=60)
    st.title("Flujo de Caja")
    st.caption("Dashboard Multi-Cliente")
    st.divider()

    empresas = cargar_empresas()
    nombres_empresas = [e["nombre"] for e in empresas]

    if not nombres_empresas:
        st.warning("No hay empresas registradas. Ve a **Configuración** para crear una.")
        empresa_sel = None
        empresa_id = None
    else:
        empresa_sel = st.selectbox(
            "🏢 Cliente / Empresa",
            nombres_empresas,
            help="Selecciona la empresa para ver o registrar datos.",
        )
        empresa_id = next(
            (e["id"] for e in empresas if e["nombre"] == empresa_sel), None
        )

    st.divider()
    pagina = st.radio(
        "📂 Navegación",
        [
            "📊 Dashboard",
            "📥 Movimientos",
            "💱 Tasas de Cambio",
            "🔍 Conciliación",
            "⚙️ Configuración",
        ],
        label_visibility="collapsed",
    )

# ──────────────────────────────────────────────
# 5. PÁGINA: CONFIGURACIÓN (Empresas, Bancos, Categorías)
# ──────────────────────────────────────────────

if pagina == "⚙️ Configuración":
    st.header("⚙️ Configuración del Sistema")

    tab_emp, tab_ban, tab_cat = st.tabs(
        ["🏢 Empresas", "🏦 Bancos / Cajas", "🏷️ Categorías"]
    )

    with tab_emp:
        st.subheader("Registrar nueva empresa")
        with st.form("form_empresa", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                emp_nombre = st.text_input("Nombre de la empresa")
                emp_rif = st.text_input("RIF")
            with col2:
                emp_dir = st.text_input("Dirección")
            if st.form_submit_button("➕ Crear Empresa", use_container_width=True):
                if emp_nombre:
                    crear_empresa(emp_nombre, emp_rif, emp_dir)
                    st.success(f"Empresa **{emp_nombre}** creada.")
                    st.rerun()
                else:
                    st.error("El nombre es obligatorio.")

        st.subheader("Empresas registradas")
        if empresas:
            df_emp = pd.DataFrame(empresas)[["nombre", "rif", "direccion"]]
            df_emp.columns = ["Empresa", "RIF", "Dirección"]
            st.dataframe(df_emp, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay empresas.")

    with tab_ban:
        if empresa_id:
            st.subheader(f"Bancos / Cajas de {empresa_sel}")
            with st.form("form_banco", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    ban_nombre = st.text_input("Nombre del banco o caja")
                with col2:
                    ban_tipo = st.selectbox(
                        "Tipo",
                        [
                            "Cuenta Corriente",
                            "Cuenta Ahorro",
                            "Pago Móvil",
                            "Punto de Venta",
                            "Caja Chica Bs",
                            "Caja Chica $",
                            "Wallet Crypto",
                            "Otro",
                        ],
                    )
                if st.form_submit_button("➕ Agregar Banco", use_container_width=True):
                    if ban_nombre:
                        crear_banco(empresa_id, ban_nombre, ban_tipo)
                        st.success(f"Banco **{ban_nombre}** agregado.")
                        st.rerun()

            bancos = cargar_bancos(empresa_id)
            if bancos:
                df_ban = pd.DataFrame(bancos)[["nombre", "tipo"]]
                df_ban.columns = ["Banco / Caja", "Tipo"]
                st.dataframe(df_ban, use_container_width=True, hide_index=True)
            else:
                st.info("No hay bancos registrados para esta empresa.")
        else:
            st.info("Selecciona una empresa primero.")

    with tab_cat:
        st.subheader("Categorías del Flujo de Caja")
        st.caption(
            "Estas categorías son globales (compartidas entre todas las empresas)."
        )
        cats = cargar_categorias()
        if cats:
            df_cat = pd.DataFrame(cats)[
                ["subclasificacion", "clasificacion", "partida_fc"]
            ]
            df_cat.columns = ["Subclasificación", "Clasificación", "Partida FC"]
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
        else:
            st.info(
                "Ejecuta el script SQL de inicialización para cargar las categorías predefinidas."
            )


# ──────────────────────────────────────────────
# 6. PÁGINA: TASAS DE CAMBIO
# ──────────────────────────────────────────────

elif pagina == "💱 Tasas de Cambio":
    st.header("💱 Tasas de Cambio Diarias")

    if not empresa_id:
        st.warning("Selecciona una empresa en la barra lateral.")
        st.stop()

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        anio_tasa = st.selectbox("Año", list(range(2026, 2020, -1)), key="anio_t")
    with col_f2:
        mes_tasa = st.selectbox(
            "Mes",
            list(range(1, 13)),
            format_func=lambda m: calendar.month_name[m],
            index=date.today().month - 1,
            key="mes_t",
        )
    with col_f3:
        st.write("")  # spacer

    st.subheader("Registrar / Actualizar Tasa")
    with st.form("form_tasa", clear_on_submit=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            t_fecha = st.date_input("Fecha", value=date.today())
        with col2:
            t_bcv = st.number_input("Tasa BCV (Bs/$)", min_value=0.0, step=0.01, format="%.4f")
        with col3:
            t_euro = st.number_input("Tasa Euro (Bs/€)", min_value=0.0, step=0.01, format="%.4f")
        with col4:
            t_binance = st.number_input("Tasa Binance (Bs/$)", min_value=0.0, step=0.01, format="%.4f")
        if st.form_submit_button("💾 Guardar Tasa", use_container_width=True):
            guardar_tasa(empresa_id, t_fecha.isoformat(), t_bcv, t_euro, t_binance)
            st.success(f"Tasa del {t_fecha} guardada.")
            st.rerun()

    tasas = cargar_tasas(empresa_id, mes_tasa, anio_tasa)
    if tasas:
        df_tasas = pd.DataFrame(tasas)[
            ["fecha", "tasa_bcv", "tasa_euro", "tasa_binance"]
        ]
        df_tasas.columns = ["Fecha", "BCV (Bs/$)", "Euro (Bs/€)", "Binance (Bs/$)"]
        st.dataframe(df_tasas, use_container_width=True, hide_index=True)

        # Gráfico de evolución
        df_chart = pd.DataFrame(tasas)
        df_chart["fecha"] = pd.to_datetime(df_chart["fecha"])
        df_chart = df_chart.sort_values("fecha")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_chart["fecha"], y=df_chart["tasa_bcv"], name="BCV", line=dict(color="#00d4aa")))
        fig.add_trace(go.Scatter(x=df_chart["fecha"], y=df_chart["tasa_euro"], name="Euro", line=dict(color="#ffa726")))
        fig.add_trace(go.Scatter(x=df_chart["fecha"], y=df_chart["tasa_binance"], name="Binance", line=dict(color="#42a5f5")))
        fig.update_layout(
            title="Evolución de Tasas",
            template="plotly_dark",
            height=350,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay tasas registradas para este período.")


# ──────────────────────────────────────────────
# 7. PÁGINA: MOVIMIENTOS
# ──────────────────────────────────────────────

elif pagina == "📥 Movimientos":
    st.header("📥 Registro de Movimientos Bancarios")

    if not empresa_id:
        st.warning("Selecciona una empresa en la barra lateral.")
        st.stop()

    bancos = cargar_bancos(empresa_id)
    categorias = cargar_categorias()

    if not bancos:
        st.warning("Primero registra al menos un banco en **Configuración**.")
        st.stop()

    nombres_bancos = {b["id"]: b["nombre"] for b in bancos}
    lista_cats = {c["id"]: f"{c['subclasificacion']} → {c['partida_fc']}" for c in categorias} if categorias else {}

    st.subheader("Nuevo Movimiento")
    with st.form("form_mov", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            m_fecha = st.date_input("Fecha", value=date.today())
            m_banco = st.selectbox("Banco / Caja", list(nombres_bancos.keys()), format_func=lambda x: nombres_bancos[x])
        with col2:
            m_ref = st.text_input("Referencia")
            m_desc = st.text_input("Descripción")
        with col3:
            m_monto = st.number_input("Monto", step=0.01, format="%.2f")
            m_moneda = st.selectbox("Moneda", ["VES", "USD", "EUR"])
        col4, col5 = st.columns(2)
        with col4:
            m_tipo = st.selectbox("Tipo", ["Ingreso", "Egreso"])
        with col5:
            cat_opciones = ["Sin categorizar"] + list(lista_cats.values())
            m_cat_label = st.selectbox("Categoría (Subclasificación → Partida)", cat_opciones)

        if st.form_submit_button("➕ Registrar Movimiento", use_container_width=True):
            cat_id = None
            partida = None
            if m_cat_label != "Sin categorizar" and categorias:
                for c in categorias:
                    label_c = f"{c['subclasificacion']} → {c['partida_fc']}"
                    if label_c == m_cat_label:
                        cat_id = c["id"]
                        partida = c["partida_fc"]
                        break

            monto_final = abs(m_monto) if m_tipo == "Ingreso" else -abs(m_monto)

            guardar_movimiento(
                {
                    "empresa_id": empresa_id,
                    "fecha": m_fecha.isoformat(),
                    "banco_id": m_banco,
                    "referencia": m_ref,
                    "descripcion": m_desc,
                    "monto": monto_final,
                    "moneda": m_moneda,
                    "tipo": m_tipo.lower(),
                    "categoria_id": cat_id,
                    "partida_fc": partida,
                }
            )
            st.success("Movimiento registrado.")
            st.rerun()

    # Filtros y tabla de movimientos
    st.divider()
    st.subheader("Movimientos registrados")
    col_fa, col_fb = st.columns(2)
    with col_fa:
        f_anio = st.selectbox("Año", list(range(2026, 2020, -1)), key="f_anio_m")
    with col_fb:
        f_mes = st.selectbox(
            "Mes",
            list(range(1, 13)),
            format_func=lambda m: calendar.month_name[m],
            index=date.today().month - 1,
            key="f_mes_m",
        )

    movs = cargar_movimientos(empresa_id, {"mes": f_mes, "anio": f_anio})
    if movs:
        filas = []
        for m in movs:
            banco_nombre = m.get("bancos", {}).get("nombre", "—") if m.get("bancos") else "—"
            cat_info = m.get("categorias", {}) or {}
            filas.append(
                {
                    "Fecha": m["fecha"],
                    "Banco": banco_nombre,
                    "Ref": m.get("referencia", ""),
                    "Descripción": m.get("descripcion", ""),
                    "Monto": m["monto"],
                    "Moneda": m.get("moneda", "VES"),
                    "Tipo": m.get("tipo", ""),
                    "Partida FC": m.get("partida_fc", "Sin categorizar"),
                    "Subclasificación": cat_info.get("subclasificacion", "—"),
                }
            )
        df_movs = pd.DataFrame(filas)
        st.dataframe(df_movs, use_container_width=True, hide_index=True)
        st.caption(f"Total: {len(filas)} movimientos")
    else:
        st.info("No hay movimientos para este período.")


# ──────────────────────────────────────────────
# 8. PÁGINA: DASHBOARD
# ──────────────────────────────────────────────

elif pagina == "📊 Dashboard":
    st.header(f"📊 Dashboard — {empresa_sel or 'Sin empresa'}")

    if not empresa_id:
        st.warning("Selecciona una empresa en la barra lateral.")
        st.stop()

    # Filtros del dashboard
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        d_anio = st.selectbox("Año", list(range(2026, 2020, -1)), key="d_anio")
    with col_d2:
        d_mes = st.selectbox(
            "Mes",
            list(range(1, 13)),
            format_func=lambda m: calendar.month_name[m],
            index=date.today().month - 1,
            key="d_mes",
        )
    with col_d3:
        bancos = cargar_bancos(empresa_id)
        banco_opciones = {"Todos": None}
        banco_opciones.update({b["nombre"]: b["id"] for b in bancos})
        d_banco_label = st.selectbox("Banco / Caja", list(banco_opciones.keys()), key="d_banco")
        d_banco_id = banco_opciones[d_banco_label]

    filtros = {"mes": d_mes, "anio": d_anio}
    if d_banco_id:
        filtros["banco_id"] = d_banco_id

    movs = cargar_movimientos(empresa_id, filtros)

    if not movs:
        st.info("No hay movimientos para este período y filtros.")
        st.stop()

    # Preparar DataFrame
    df = pd.DataFrame(movs)
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["banco_nombre"] = df.apply(
        lambda r: r.get("bancos", {}).get("nombre", "—") if isinstance(r.get("bancos"), dict) else "—",
        axis=1,
    )
    df["partida_fc"] = df["partida_fc"].fillna("Sin categorizar")

    ingresos = df[df["monto"] > 0]["monto"].sum()
    egresos = df[df["monto"] < 0]["monto"].sum()
    flujo_neto = ingresos + egresos
    total_movs = len(df)
    sin_cat = len(df[df["partida_fc"] == "Sin categorizar"])
    prom_ingreso = df[df["monto"] > 0]["monto"].mean() if len(df[df["monto"] > 0]) > 0 else 0
    prom_egreso = df[df["monto"] < 0]["monto"].mean() if len(df[df["monto"] < 0]) > 0 else 0

    # Tarjetas KPI
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(tarjeta_metrica("Ingresos del Período", f"Bs {ingresos:,.2f}", "positive"), unsafe_allow_html=True)
    with c2:
        st.markdown(tarjeta_metrica("Egresos del Período", f"Bs {abs(egresos):,.2f}", "negative"), unsafe_allow_html=True)
    with c3:
        clase_fn = "positive" if flujo_neto >= 0 else "negative"
        st.markdown(tarjeta_metrica("Flujo Neto", f"Bs {flujo_neto:,.2f}", clase_fn), unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3)
    with c4:
        st.markdown(tarjeta_metrica("Prom. Ingreso", f"Bs {prom_ingreso:,.2f}", "neutral"), unsafe_allow_html=True)
    with c5:
        st.markdown(tarjeta_metrica("Prom. Egreso", f"Bs {abs(prom_egreso):,.2f}", "neutral"), unsafe_allow_html=True)
    with c6:
        clase_sc = "warning" if sin_cat > 0 else "neutral"
        st.markdown(tarjeta_metrica("Sin Categorizar", str(sin_cat), clase_sc), unsafe_allow_html=True)

    st.write("")

    # Flujo por Partida
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("Flujo por Partida FC")
        df_partida = (
            df.groupby("partida_fc")["monto"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"partida_fc": "Partida", "sum": "Monto", "count": "Movimientos"})
            .sort_values("Monto")
        )
        df_partida["% del Total"] = (df_partida["Monto"].abs() / df_partida["Monto"].abs().sum() * 100).round(1)

        fig_partida = px.bar(
            df_partida,
            y="Partida",
            x="Monto",
            orientation="h",
            color="Monto",
            color_continuous_scale=["#ff6b6b", "#ffa726", "#00d4aa"],
            text=df_partida["Monto"].apply(lambda x: f"Bs {x:,.0f}"),
        )
        fig_partida.update_layout(
            template="plotly_dark", height=400, showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig_partida, use_container_width=True)

    with col_g2:
        st.subheader("Distribución por Partida")
        df_pie = df_partida.copy()
        df_pie["Monto_abs"] = df_pie["Monto"].abs()
        fig_pie = px.pie(
            df_pie,
            values="Monto_abs",
            names="Partida",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_pie.update_layout(template="plotly_dark", height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    # Flujo por Banco
    st.subheader("Flujo por Banco / Caja")
    col_b1, col_b2 = st.columns(2)

    with col_b1:
        df_banco = (
            df.groupby("banco_nombre")["monto"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"banco_nombre": "Banco", "sum": "Saldo Neto", "count": "Movimientos"})
        )
        st.dataframe(df_banco, use_container_width=True, hide_index=True)

    with col_b2:
        fig_banco = px.bar(
            df_banco,
            x="Banco",
            y="Saldo Neto",
            color="Saldo Neto",
            color_continuous_scale=["#ff6b6b", "#00d4aa"],
            text=df_banco["Saldo Neto"].apply(lambda x: f"Bs {x:,.0f}"),
        )
        fig_banco.update_layout(
            template="plotly_dark", height=300, showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig_banco, use_container_width=True)

    # Flujo diario acumulado
    st.subheader("Flujo Diario y Acumulado")
    df_diario = df.groupby(df["fecha"].dt.date)["monto"].sum().reset_index()
    df_diario.columns = ["Fecha", "Flujo Diario"]
    df_diario = df_diario.sort_values("Fecha")
    df_diario["Acumulado"] = df_diario["Flujo Diario"].cumsum()

    fig_diario = go.Figure()
    fig_diario.add_trace(
        go.Bar(x=df_diario["Fecha"], y=df_diario["Flujo Diario"], name="Flujo Diario",
               marker_color=df_diario["Flujo Diario"].apply(lambda x: "#00d4aa" if x >= 0 else "#ff6b6b"))
    )
    fig_diario.add_trace(
        go.Scatter(x=df_diario["Fecha"], y=df_diario["Acumulado"], name="Acumulado",
                   line=dict(color="#42a5f5", width=3))
    )
    fig_diario.update_layout(
        template="plotly_dark", height=350, barmode="overlay",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig_diario, use_container_width=True)


# ──────────────────────────────────────────────
# 9. PÁGINA: CONCILIACIÓN BANCARIA
# ──────────────────────────────────────────────

elif pagina == "🔍 Conciliación":
    st.header("🔍 Conciliación Bancaria y Auditoría")

    if not empresa_id:
        st.warning("Selecciona una empresa en la barra lateral.")
        st.stop()

    bancos = cargar_bancos(empresa_id)
    if not bancos:
        st.warning("No hay bancos registrados.")
        st.stop()

    tab_conc, tab_aud = st.tabs(["📋 Conciliación", "⚠️ Excepciones"])

    with tab_conc:
        st.subheader("Estado de Conciliación por Banco")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_anio = st.selectbox("Año", list(range(2026, 2020, -1)), key="c_anio")
        with col_c2:
            c_mes = st.selectbox(
                "Mes",
                list(range(1, 13)),
                format_func=lambda m: calendar.month_name[m],
                index=date.today().month - 1,
                key="c_mes",
            )

        for banco in bancos:
            movs_b = cargar_movimientos(
                empresa_id,
                {"mes": c_mes, "anio": c_anio, "banco_id": banco["id"]},
            )
            if movs_b:
                df_b = pd.DataFrame(movs_b)
                df_b["monto"] = pd.to_numeric(df_b["monto"], errors="coerce").fillna(0)
                ing = df_b[df_b["monto"] > 0]["monto"].sum()
                egr = df_b[df_b["monto"] < 0]["monto"].sum()
                saldo = ing + egr
                n_movs = len(df_b)

                with st.expander(f"🏦 {banco['nombre']} — Saldo: Bs {saldo:,.2f}  ({n_movs} movs)", expanded=False):
                    c_a, c_b, c_c = st.columns(3)
                    c_a.metric("Ingresos", f"Bs {ing:,.2f}")
                    c_b.metric("Egresos", f"Bs {abs(egr):,.2f}")
                    c_c.metric("Saldo", f"Bs {saldo:,.2f}", delta=f"Bs {saldo:,.2f}")

                    st.write("**Saldo según estado de cuenta (manual):**")
                    saldo_ec = st.number_input(
                        "Saldo Estado de Cuenta",
                        value=0.0,
                        step=0.01,
                        format="%.2f",
                        key=f"saldo_ec_{banco['id']}",
                    )
                    diferencia = saldo - saldo_ec
                    if abs(diferencia) < 0.01:
                        st.success("✅ Conciliado — sin diferencia.")
                    else:
                        st.error(f"❌ Diferencia: Bs {diferencia:,.2f}")
            else:
                st.info(f"🏦 {banco['nombre']} — Sin movimientos en el período.")

    with tab_aud:
        st.subheader("Excepciones y Alertas")

        movs_all = cargar_movimientos(empresa_id, {"mes": c_mes, "anio": c_anio})
        if movs_all:
            df_all = pd.DataFrame(movs_all)
            df_all["monto"] = pd.to_numeric(df_all["monto"], errors="coerce").fillna(0)

            # 1. Sin categorizar
            sin_cat = df_all[df_all["partida_fc"].isna() | (df_all["partida_fc"] == "")]
            st.write(f"**🏷️ Movimientos sin categorizar:** {len(sin_cat)}")
            if len(sin_cat) > 0:
                filas_sc = []
                for _, r in sin_cat.iterrows():
                    filas_sc.append(
                        {
                            "Fecha": r["fecha"],
                            "Descripción": r.get("descripcion", ""),
                            "Monto": r["monto"],
                            "Ref": r.get("referencia", ""),
                        }
                    )
                st.dataframe(pd.DataFrame(filas_sc), use_container_width=True, hide_index=True)

            # 2. Posibles duplicados (misma fecha + mismo monto)
            dup = df_all[df_all.duplicated(subset=["fecha", "monto"], keep=False)]
            st.write(f"**🔁 Posibles duplicados (fecha + monto):** {len(dup)}")
            if len(dup) > 0:
                filas_dup = []
                for _, r in dup.iterrows():
                    filas_dup.append(
                        {
                            "Fecha": r["fecha"],
                            "Descripción": r.get("descripcion", ""),
                            "Monto": r["monto"],
                            "Ref": r.get("referencia", ""),
                        }
                    )
                st.dataframe(pd.DataFrame(filas_dup), use_container_width=True, hide_index=True)

            # 3. Montos atípicos (> 2 desviaciones estándar)
            mean_abs = df_all["monto"].abs().mean()
            std_abs = df_all["monto"].abs().std()
            if std_abs > 0:
                atipicos = df_all[df_all["monto"].abs() > mean_abs + 2 * std_abs]
                st.write(f"**📈 Montos atípicos (>2σ):** {len(atipicos)}")
                if len(atipicos) > 0:
                    filas_at = []
                    for _, r in atipicos.iterrows():
                        filas_at.append(
                            {
                                "Fecha": r["fecha"],
                                "Descripción": r.get("descripcion", ""),
                                "Monto": r["monto"],
                                "Ref": r.get("referencia", ""),
                            }
                        )
                    st.dataframe(pd.DataFrame(filas_at), use_container_width=True, hide_index=True)
        else:
            st.info("No hay movimientos para auditar en este período.")


# ──────────────────────────────────────────────
# 10. FOOTER
# ──────────────────────────────────────────────
st.divider()
st.caption("Flujo de Caja Dashboard v1.0 — Desarrollado para @contabilidad_22")
