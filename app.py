"""
FLUJO DE CAJA & DASHBOARD — Aplicación Multi-Cliente con Login
==============================================================
Streamlit + Supabase (PostgreSQL)
Autor: Darwin / contabilidadenlinea15@gmail.com
v2.0 — Con autenticación por usuario y roles (admin/cliente)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import date, datetime, timedelta
import calendar
import hashlib
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
# 2. SISTEMA DE AUTENTICACIÓN
# ──────────────────────────────────────────────

def hash_password(password):
    """Genera hash SHA-256 de la contraseña."""
    return hashlib.sha256(password.encode()).hexdigest()


def verificar_login(usuario, password):
    """Verifica credenciales y devuelve datos del usuario o None."""
    pwd_hash = hash_password(password)
    resp = (
        supabase.table("usuarios")
        .select("*, empresas(id, nombre)")
        .eq("usuario", usuario)
        .eq("password_hash", pwd_hash)
        .eq("activo", True)
        .execute()
    )
    if resp.data and len(resp.data) > 0:
        return resp.data[0]
    return None


def crear_usuario(usuario, password, nombre_completo, rol, empresa_id=None):
    """Crea un nuevo usuario."""
    pwd_hash = hash_password(password)
    data = {
        "usuario": usuario,
        "password_hash": pwd_hash,
        "nombre_completo": nombre_completo,
        "rol": rol,
        "empresa_id": empresa_id,
        "activo": True,
    }
    supabase.table("usuarios").insert(data).execute()


def cargar_usuarios():
    """Lista todos los usuarios."""
    resp = (
        supabase.table("usuarios")
        .select("*, empresas(nombre)")
        .order("nombre_completo")
        .execute()
    )
    return resp.data


def actualizar_usuario(user_id, data):
    """Actualiza datos de un usuario."""
    supabase.table("usuarios").update(data).eq("id", user_id).execute()


def pantalla_login():
    """Muestra la pantalla de login y retorna True si el usuario se autentica."""
    st.markdown(
        """
        <div style="text-align:center; padding: 40px 0 20px 0;">
            <h1 style="color: #1a1a2e;">💰 Flujo de Caja</h1>
            <p style="color: #666; font-size: 1.1rem;">Dashboard Multi-Cliente</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_center, col_right = st.columns([1, 1.5, 1])
    with col_center:
        with st.form("login_form"):
            st.subheader("Iniciar Sesión")
            usuario = st.text_input("👤 Usuario", placeholder="Tu nombre de usuario")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="Tu contraseña")
            submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")

            if submitted:
                if usuario and password:
                    user_data = verificar_login(usuario, password)
                    if user_data:
                        st.session_state["authenticated"] = True
                        st.session_state["user"] = user_data
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                else:
                    st.warning("Ingresa usuario y contraseña.")

        st.caption("Contacta al administrador si no tienes cuenta.")


def obtener_empresas_usuario(user_data):
    """Devuelve las empresas que el usuario puede ver según su rol."""
    if user_data["rol"] == "admin":
        return cargar_empresas()
    else:
        # Cliente solo ve su empresa asignada
        if user_data.get("empresa_id"):
            resp = (
                supabase.table("empresas")
                .select("*")
                .eq("id", user_data["empresa_id"])
                .execute()
            )
            return resp.data
        return []


# ──────────────────────────────────────────────
# VERIFICAR AUTENTICACIÓN
# ──────────────────────────────────────────────

# Inicializar sesión
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Si no está autenticado, mostrar login
if not st.session_state["authenticated"]:
    pantalla_login()
    st.stop()

# Usuario autenticado — obtener datos
user = st.session_state["user"]
es_admin = user["rol"] == "admin"


# ──────────────────────────────────────────────
# 3. FUNCIONES AUXILIARES DE BASE DE DATOS
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


def guardar_movimientos_lote(lista_movimientos):
    """Inserta múltiples movimientos de una vez."""
    supabase.table("movimientos").insert(lista_movimientos).execute()


# ──────────────────────────────────────────────
# 3B. AUTO-CATEGORIZACIÓN POR PALABRAS CLAVE
# ──────────────────────────────────────────────

REGLAS_CATEGORIA = [
    # (palabras clave en descripción, subclasificacion que debe coincidir en BD)
    # INGRESOS
    (["cobranza", "cobro a cliente"], "Cobros a clientes"),
    (["venta de contado", "venta contado", "venta efectivo"], "Ventas de contado"),
    (["anticipo cliente", "adelanto cliente"], "Anticipos de clientes"),
    (["nota de credito recibida", "nota credito"], "Notas de crédito recibidas"),
    (["interes bancario", "intereses ganados"], "Intereses bancarios"),
    (["ganancia cambiaria", "diferencial cambiario positivo"], "Ganancia cambiaria"),
    (["dividendo"], "Dividendos recibidos"),
    (["alquiler recibido", "ingreso alquiler", "canon arrendamiento"], "Ingresos por alquiler"),
    (["recuperacion gasto", "reintegro"], "Recuperación de gastos"),
    # EGRESOS - NÓMINA
    (["nomina", "sueldo", "salario", "quincena"], "Sueldos y salarios"),
    (["prestacion social", "antiguedad"], "Prestaciones sociales"),
    (["utilidad", "bonificacion", "bono"], "Utilidades / Bonificaciones"),
    (["ivss", "faov", "inces", "seguro social"], "IVSS / FAOV / INCES"),
    (["vacacion"], "Vacaciones"),
    (["cesta ticket", "alimentacion", "cestaticket"], "Alimentación / Cesta ticket"),
    # EGRESOS - OPERATIVOS
    (["alquiler local", "canon alquiler", "arrendamiento local"], "Alquiler de local"),
    (["electricidad", "agua", "aseo", "servicio publico"], "Servicios públicos"),
    (["internet", "telefono", "telecomunicacion", "cantv", "movistar", "digitel"], "Internet / Telecomunicaciones"),
    (["seguro", "poliza"], "Seguros"),
    (["mantenimiento", "reparacion"], "Mantenimiento"),
    # EGRESOS - COMPRAS
    (["compra mercancia", "compra inventario", "mercaderia"], "Compras de mercancía"),
    (["materia prima"], "Compras de materia prima"),
    (["flete", "transporte", "envio", "delivery"], "Fletes y transporte"),
    (["pago proveedor", "proveedor"], "Pagos a proveedores"),
    # EGRESOS - IMPUESTOS
    (["islr", "impuesto renta"], "ISLR"),
    (["iva por pagar", "iva debito", "iva declaracion"], "IVA por pagar"),
    (["impuesto municipal", "patente industria"], "Impuestos municipales"),
    (["tasa", "contribucion", "timbre fiscal"], "Tasas y contribuciones"),
    (["retencion islr", "ret islr"], "Retenciones ISLR"),
    (["retencion iva", "ret iva"], "Retenciones IVA"),
    # EGRESOS - FINANCIEROS
    (["comision bancaria", "comision banco", "comisiones bancarias", "igtf"], "Comisiones bancarias"),
    (["interes prestamo", "intereses pagados"], "Intereses por préstamos"),
    (["perdida cambiaria", "diferencial cambiario negativo"], "Pérdida cambiaria"),
    (["itf", "igtf", "impuesto transaccion"], "ITF / IGTF"),
    # EGRESOS - ADMINISTRATIVOS
    (["papeleria", "utiles oficina"], "Papelería y útiles"),
    (["honorario", "profesional", "consultoria", "asesoria"], "Honorarios profesionales"),
    (["representacion", "viaje", "viatico"], "Gastos de representación"),
    (["suscripcion", "software", "licencia"], "Suscripciones y software"),
    (["gasto legal", "abogado", "notaria", "registro"], "Gastos legales"),
    # INVERSIONES
    (["compra equipo", "computador", "maquinaria"], "Compra de equipos"),
    (["compra vehiculo", "vehiculo"], "Compra de vehículos"),
    (["mejora local", "remodelacion", "ampliacion"], "Mejoras al local"),
    (["prestamo otorgado", "prestamo dado"], "Préstamos otorgados"),
    # FINANCIAMIENTO
    (["prestamo recibido", "credito recibido"], "Préstamos recibidos"),
    (["pago prestamo", "cuota prestamo", "amortizacion"], "Pago de préstamos"),
    (["aporte capital", "capitalizacion"], "Aportes de capital"),
    (["retiro capital", "dividendo pagado", "distribucion utilidades"], "Retiros de capital / Dividendos"),
]


def auto_categorizar(descripcion, categorias_bd):
    """Intenta asignar categoría automáticamente según palabras clave en la descripción."""
    if not descripcion or not categorias_bd:
        return None, None
    desc_lower = descripcion.lower().strip()

    for palabras_clave, subclasif_objetivo in REGLAS_CATEGORIA:
        for palabra in palabras_clave:
            if palabra in desc_lower:
                # Buscar la categoría en BD
                for cat in categorias_bd:
                    if cat["subclasificacion"] == subclasif_objetivo:
                        return cat["id"], cat["partida_fc"]
    return None, None


# ──────────────────────────────────────────────
# 4. ESTILOS PERSONALIZADOS
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
# 5. SIDEBAR — USUARIO, SELECTOR DE EMPRESA + NAVEGACIÓN
# ──────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/cash-in-hand.png", width=60)
    st.title("Flujo de Caja")
    st.caption("Dashboard Multi-Cliente")
    st.divider()

    # Info del usuario logueado
    st.markdown(f"👤 **{user['nombre_completo']}**")
    rol_label = "🔑 Administrador" if es_admin else "👁️ Cliente"
    st.caption(rol_label)

    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user"] = None
        st.rerun()

    st.divider()

    # Empresas según el rol
    empresas = obtener_empresas_usuario(user)
    nombres_empresas = [e["nombre"] for e in empresas]

    if not nombres_empresas:
        st.warning("No tienes empresas asignadas.")
        empresa_sel = None
        empresa_id = None
    elif len(nombres_empresas) == 1:
        # Cliente con una sola empresa — no mostrar selector
        empresa_sel = nombres_empresas[0]
        empresa_id = empresas[0]["id"]
        st.info(f"🏢 **{empresa_sel}**")
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

    # Navegación — admin ve todo, cliente ve solo lectura
    if es_admin:
        pagina = st.radio(
            "📂 Navegación",
            [
                "📊 Dashboard",
                "📥 Movimientos",
                "💱 Tasas de Cambio",
                "🔍 Conciliación",
                "⚙️ Configuración",
                "👥 Usuarios",
            ],
            label_visibility="collapsed",
        )
    else:
        pagina = st.radio(
            "📂 Navegación",
            [
                "📊 Dashboard",
                "📥 Movimientos",
                "💱 Tasas de Cambio",
                "🔍 Conciliación",
            ],
            label_visibility="collapsed",
        )

# ──────────────────────────────────────────────
# 6. PÁGINA: USUARIOS (solo admin)
# ──────────────────────────────────────────────

if pagina == "👥 Usuarios" and es_admin:
    st.header("👥 Gestión de Usuarios")

    tab_nuevo, tab_lista = st.tabs(["➕ Nuevo Usuario", "📋 Usuarios Registrados"])

    with tab_nuevo:
        st.subheader("Crear nuevo usuario")
        todas_empresas = cargar_empresas()

        with st.form("form_usuario", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                u_nombre = st.text_input("Nombre completo")
                u_usuario = st.text_input("Nombre de usuario (para login)", help="Sin espacios, todo en minúsculas.")
            with col2:
                u_password = st.text_input("Contraseña", type="password")
                u_rol = st.selectbox("Rol", ["cliente", "admin"], help="**Admin**: ve todas las empresas y puede crear usuarios. **Cliente**: solo ve su empresa asignada.")

            if u_rol == "cliente" and todas_empresas:
                u_empresa = st.selectbox(
                    "Empresa asignada",
                    [e["nombre"] for e in todas_empresas],
                    help="El cliente solo podrá ver los datos de esta empresa.",
                )
            else:
                u_empresa = None

            if st.form_submit_button("➕ Crear Usuario", use_container_width=True):
                if u_nombre and u_usuario and u_password:
                    empresa_asig_id = None
                    if u_rol == "cliente" and u_empresa and todas_empresas:
                        empresa_asig_id = next(
                            (e["id"] for e in todas_empresas if e["nombre"] == u_empresa), None
                        )

                    try:
                        crear_usuario(u_usuario.lower().strip(), u_password, u_nombre, u_rol, empresa_asig_id)
                        st.success(f"Usuario **{u_usuario}** creado como **{u_rol}**.")
                        st.rerun()
                    except Exception as e:
                        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                            st.error("Ese nombre de usuario ya existe. Elige otro.")
                        else:
                            st.error(f"Error: {e}")
                else:
                    st.error("Todos los campos son obligatorios.")

    with tab_lista:
        st.subheader("Usuarios registrados")
        usuarios = cargar_usuarios()
        if usuarios:
            filas_u = []
            for u in usuarios:
                emp_nombre = u.get("empresas", {})
                if isinstance(emp_nombre, dict):
                    emp_nombre = emp_nombre.get("nombre", "Todas (Admin)")
                else:
                    emp_nombre = "Todas (Admin)"
                filas_u.append({
                    "Nombre": u["nombre_completo"],
                    "Usuario": u["usuario"],
                    "Rol": u["rol"].upper(),
                    "Empresa": emp_nombre,
                    "Activo": "✅" if u.get("activo", True) else "❌",
                })
            st.dataframe(pd.DataFrame(filas_u), use_container_width=True, hide_index=True)

            # Cambiar contraseña de usuario
            st.divider()
            st.subheader("Cambiar contraseña")
            with st.form("form_cambiar_pwd"):
                u_sel = st.selectbox("Usuario", [u["usuario"] for u in usuarios])
                nueva_pwd = st.text_input("Nueva contraseña", type="password")
                if st.form_submit_button("🔑 Cambiar Contraseña"):
                    if nueva_pwd:
                        uid = next((u["id"] for u in usuarios if u["usuario"] == u_sel), None)
                        if uid:
                            actualizar_usuario(uid, {"password_hash": hash_password(nueva_pwd)})
                            st.success(f"Contraseña de **{u_sel}** actualizada.")
                    else:
                        st.error("Escribe la nueva contraseña.")
        else:
            st.info("No hay usuarios registrados.")


# ──────────────────────────────────────────────
# 7. PÁGINA: CONFIGURACIÓN (Empresas, Bancos, Categorías) — solo admin
# ──────────────────────────────────────────────

elif pagina == "⚙️ Configuración":
    if not es_admin:
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()

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
# 8. PÁGINA: TASAS DE CAMBIO
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

    # Solo admin puede registrar tasas
    if es_admin:
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
# 9. PÁGINA: MOVIMIENTOS
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
    nombres_bancos_inv = {b["nombre"].upper().strip(): b["id"] for b in bancos}
    lista_cats = {c["id"]: f"{c['subclasificacion']} → {c['partida_fc']}" for c in categorias} if categorias else {}

    # Pestañas: Manual | Importar | Historial
    if es_admin:
        tab_manual, tab_importar, tab_historial = st.tabs(
            ["✏️ Registro Manual", "📤 Importar Archivo", "📋 Historial"]
        )
    else:
        tab_historial = st.container()
        tab_manual = None
        tab_importar = None

    # ── PESTAÑA: REGISTRO MANUAL (solo admin) ──
    if es_admin:
        with tab_manual:
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

    # ── PESTAÑA: IMPORTAR ARCHIVO (solo admin) ──
    if es_admin:
        with tab_importar:
            st.subheader("📤 Importar Movimientos desde Archivo")

            # Guía del formato requerido
            with st.expander("📖 Formato requerido del archivo — Leer antes de importar", expanded=True):
                st.markdown(
                    """
**El archivo debe tener estas columnas (exactamente con estos nombres):**

| # | Columna | Obligatoria | Descripción | Ejemplo |
|---|---------|-------------|-------------|---------|
| 1 | `FECHA` | ✅ Sí | Fecha del movimiento (DD/MM/AAAA o AAAA-MM-DD) | `20/07/2026` |
| 2 | `BANCO` | ✅ Sí | Nombre del banco/caja, debe coincidir con los registrados | `Mercantil` |
| 3 | `REFERENCIA` | ❌ No | Número de referencia bancaria | `0014502001199` |
| 4 | `DESCRIPCION` | ✅ Sí | Descripción del movimiento | `INGRESOS POR COBRANZAS` |
| 5 | `MONTO` | ✅ Sí | Monto con signo: positivo = ingreso, negativo = egreso | `1028353.5` o `-56.18` |
| 6 | `MONEDA` | ❌ No | Moneda (VES, USD, EUR). Si no existe, se asume VES | `Bs` o `USD` |

**Formatos aceptados:** `.xlsx` (Excel) y `.csv` (texto separado por comas o punto y coma).

**Sobre el MONTO:** los ingresos van en positivo y los egresos en negativo, tal como aparecen en tu estado de cuenta.

**Sobre la MONEDA:** puedes escribir `Bs`, `VES`, `bolivares` para bolívares; `USD`, `$`, `dolares` para dólares; `EUR`, `€`, `euros` para euros. Si la columna no existe, se asume VES.

**La categoría se asigna automáticamente** según la descripción (ej: "COBRANZA" → Ingresos por Ventas, "COMISIONES BANCARIAS" → Gastos Bancarios). Lo que no pueda clasificar queda como "Sin categorizar" para que lo ajustes después.
                    """
                )

                # Botón para descargar plantilla de ejemplo
                plantilla_csv = "FECHA,BANCO,REFERENCIA,DESCRIPCION,MONTO,MONEDA\n20/07/2026,Mercantil,0014502001198,INGRESOS POR COBRANZAS,1028353.50,Bs\n20/07/2026,Mercantil,0095402001198,COMISIONES BANCARIAS IGTF,-79235.13,Bs\n17/07/2026,BINANCE,0014502001197,INGRESOS POR COBRANZAS,7490.25,USD\n"
                st.download_button(
                    "⬇️ Descargar plantilla de ejemplo (.csv)",
                    data=plantilla_csv,
                    file_name="plantilla_movimientos.csv",
                    mime="text/csv",
                )

            st.divider()

            # Bancos registrados (referencia para el usuario)
            st.caption("🏦 **Bancos registrados en esta empresa** (el nombre en tu archivo debe coincidir con alguno de estos):")
            st.code(", ".join(sorted([b["nombre"] for b in bancos])))

            # Upload del archivo
            archivo = st.file_uploader(
                "Selecciona tu archivo Excel o CSV",
                type=["xlsx", "xls", "csv", "txt"],
                help="Arrastra o selecciona el archivo con los movimientos a importar.",
            )

            if archivo is not None:
                # Leer el archivo
                try:
                    if archivo.name.endswith((".csv", ".txt")):
                        # Intentar detectar separador
                        import io
                        contenido = archivo.read().decode("utf-8", errors="replace")
                        archivo.seek(0)
                        if ";" in contenido[:500]:
                            df_imp = pd.read_csv(io.StringIO(contenido), sep=";", dtype=str)
                        else:
                            df_imp = pd.read_csv(io.StringIO(contenido), sep=",", dtype=str)
                    else:
                        df_imp = pd.read_excel(archivo, dtype=str)
                except Exception as e:
                    st.error(f"Error al leer el archivo: {e}")
                    st.stop()

                # Normalizar nombres de columnas
                df_imp.columns = (
                    df_imp.columns.str.strip()
                    .str.upper()
                    .str.replace("Á", "A").str.replace("É", "E").str.replace("Í", "I")
                    .str.replace("Ó", "O").str.replace("Ú", "U").str.replace("Ñ", "N")
                )

                # Mapear nombres alternativos de columnas
                col_map = {}
                for col in df_imp.columns:
                    col_clean = col.strip()
                    if col_clean in ("FECHA", "DATE"):
                        col_map[col] = "FECHA"
                    elif col_clean in ("BANCO", "BANCO / CAJA", "BANCO/CAJA", "BANCO_CAJA"):
                        col_map[col] = "BANCO"
                    elif col_clean in ("REFERENCIA", "REF", "NUMERO REFERENCIA", "NRO REFERENCIA"):
                        col_map[col] = "REFERENCIA"
                    elif col_clean in ("DESCRIPCION", "DESCRIPCION SEGUN BANCO", "CONCEPTO", "DETALLE"):
                        col_map[col] = "DESCRIPCION"
                    elif col_clean in ("MONTO", "MONTO (MONEDA DE LA CUENTA)", "IMPORTE", "AMOUNT", "VALOR"):
                        col_map[col] = "MONTO"
                    elif col_clean in ("MONEDA", "MONEDA CUENTA", "CURRENCY"):
                        col_map[col] = "MONEDA"
                df_imp = df_imp.rename(columns=col_map)

                # Verificar columnas obligatorias
                cols_requeridas = ["FECHA", "BANCO", "DESCRIPCION", "MONTO"]
                cols_faltantes = [c for c in cols_requeridas if c not in df_imp.columns]

                if cols_faltantes:
                    st.error(
                        f"❌ Faltan columnas obligatorias: **{', '.join(cols_faltantes)}**. "
                        f"Tu archivo tiene: {', '.join(df_imp.columns.tolist())}. "
                        f"Revisa la guía de formato arriba."
                    )
                    st.stop()

                # Eliminar filas completamente vacías
                df_imp = df_imp.dropna(how="all").reset_index(drop=True)

                # Limpiar datos
                df_imp["MONTO"] = (
                    df_imp["MONTO"]
                    .str.replace(",", ".", regex=False)
                    .str.replace(" ", "", regex=False)
                    .str.strip()
                )
                df_imp["MONTO"] = pd.to_numeric(df_imp["MONTO"], errors="coerce")

                # Parsear fechas (soportar varios formatos)
                def parsear_fecha(val):
                    if pd.isna(val) or str(val).strip() == "":
                        return None
                    val = str(val).strip()
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y"):
                        try:
                            return datetime.strptime(val, fmt).date()
                        except ValueError:
                            continue
                    try:
                        return pd.to_datetime(val).date()
                    except Exception:
                        return None

                df_imp["FECHA_PARSED"] = df_imp["FECHA"].apply(parsear_fecha)

                # Normalizar moneda
                def normalizar_moneda(val):
                    if pd.isna(val) or str(val).strip() == "":
                        return "VES"
                    v = str(val).upper().strip()
                    if v in ("BS", "VES", "BOLIVARES", "BOLIVAR", "BSF", "BSS"):
                        return "VES"
                    elif v in ("USD", "$", "DOLARES", "DOLAR"):
                        return "USD"
                    elif v in ("EUR", "€", "EUROS", "EURO"):
                        return "EUR"
                    return "VES"

                if "MONEDA" in df_imp.columns:
                    df_imp["MONEDA_NORM"] = df_imp["MONEDA"].apply(normalizar_moneda)
                else:
                    df_imp["MONEDA_NORM"] = "VES"

                if "REFERENCIA" not in df_imp.columns:
                    df_imp["REFERENCIA"] = ""

                # Buscar banco_id para cada fila
                def buscar_banco_id(nombre_banco):
                    if pd.isna(nombre_banco):
                        return None
                    nb = str(nombre_banco).upper().strip()
                    # Buscar coincidencia exacta
                    if nb in nombres_bancos_inv:
                        return nombres_bancos_inv[nb]
                    # Buscar coincidencia parcial
                    for key, bid in nombres_bancos_inv.items():
                        if nb in key or key in nb:
                            return bid
                    return None

                df_imp["BANCO_ID"] = df_imp["BANCO"].apply(buscar_banco_id)

                # Auto-categorizar
                def cat_row(desc):
                    cid, pfc = auto_categorizar(desc, categorias)
                    return pd.Series({"CAT_ID": cid, "PARTIDA_FC": pfc})

                df_cats = df_imp["DESCRIPCION"].apply(cat_row)
                df_imp["CAT_ID"] = df_cats["CAT_ID"]
                df_imp["PARTIDA_FC"] = df_cats["PARTIDA_FC"]
                df_imp["PARTIDA_FC"] = df_imp["PARTIDA_FC"].fillna("Sin categorizar")

                # Determinar tipo
                df_imp["TIPO"] = df_imp["MONTO"].apply(lambda x: "ingreso" if pd.notna(x) and x >= 0 else "egreso")

                # ── Validación ──
                errores = []
                filas_invalidas = 0

                fechas_nulas = df_imp["FECHA_PARSED"].isna().sum()
                if fechas_nulas > 0:
                    errores.append(f"⚠️ {fechas_nulas} fila(s) con fecha inválida o vacía — serán excluidas.")

                montos_nulos = df_imp["MONTO"].isna().sum()
                if montos_nulos > 0:
                    errores.append(f"⚠️ {montos_nulos} fila(s) con monto inválido — serán excluidas.")

                bancos_no_encontrados = df_imp["BANCO_ID"].isna().sum()
                if bancos_no_encontrados > 0:
                    bancos_desconocidos = df_imp[df_imp["BANCO_ID"].isna()]["BANCO"].unique()
                    errores.append(
                        f"⚠️ {bancos_no_encontrados} fila(s) con banco no reconocido: "
                        f"**{', '.join(str(b) for b in bancos_desconocidos)}** — serán excluidas. "
                        f"Verifica que los nombres coincidan con los bancos registrados."
                    )

                # Filas válidas
                df_validas = df_imp[
                    df_imp["FECHA_PARSED"].notna()
                    & df_imp["MONTO"].notna()
                    & df_imp["BANCO_ID"].notna()
                ].copy()

                filas_invalidas = len(df_imp) - len(df_validas)

                # Mostrar errores si hay
                for err in errores:
                    st.warning(err)

                # Resumen y vista previa
                sin_cat_count = len(df_validas[df_validas["PARTIDA_FC"] == "Sin categorizar"])
                cat_count = len(df_validas) - sin_cat_count

                st.success(
                    f"✅ **{len(df_validas)}** movimientos listos para importar "
                    f"({cat_count} categorizados automáticamente, {sin_cat_count} sin categorizar)"
                )
                if filas_invalidas > 0:
                    st.caption(f"⚠️ {filas_invalidas} filas excluidas por datos inválidos.")

                # Vista previa
                st.subheader("Vista previa de los movimientos a importar")
                preview = df_validas[["FECHA", "BANCO", "REFERENCIA", "DESCRIPCION", "MONTO", "MONEDA_NORM", "TIPO", "PARTIDA_FC"]].copy()
                preview.columns = ["Fecha", "Banco", "Referencia", "Descripción", "Monto", "Moneda", "Tipo", "Categoría Asignada"]
                st.dataframe(preview, use_container_width=True, hide_index=True)

                # Resumen por categoría
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    st.caption("**Resumen por categoría:**")
                    resumen_cat = df_validas.groupby("PARTIDA_FC")["MONTO"].agg(["sum", "count"]).reset_index()
                    resumen_cat.columns = ["Partida FC", "Monto Total", "Movimientos"]
                    resumen_cat = resumen_cat.sort_values("Monto Total")
                    st.dataframe(resumen_cat, use_container_width=True, hide_index=True)
                with col_r2:
                    st.caption("**Resumen por banco:**")
                    resumen_ban = df_validas.groupby("BANCO")["MONTO"].agg(["sum", "count"]).reset_index()
                    resumen_ban.columns = ["Banco", "Monto Total", "Movimientos"]
                    st.dataframe(resumen_ban, use_container_width=True, hide_index=True)

                # Botón de importación
                st.divider()
                if len(df_validas) > 0:
                    if st.button(
                        f"✅ Confirmar importación de {len(df_validas)} movimientos",
                        use_container_width=True,
                        type="primary",
                    ):
                        # Preparar datos para insertar
                        registros = []
                        for _, row in df_validas.iterrows():
                            registros.append(
                                {
                                    "empresa_id": empresa_id,
                                    "fecha": row["FECHA_PARSED"].isoformat(),
                                    "banco_id": row["BANCO_ID"],
                                    "referencia": str(row.get("REFERENCIA", "")).strip() if pd.notna(row.get("REFERENCIA")) else "",
                                    "descripcion": str(row["DESCRIPCION"]).strip(),
                                    "monto": float(row["MONTO"]),
                                    "moneda": row["MONEDA_NORM"],
                                    "tipo": row["TIPO"],
                                    "categoria_id": row["CAT_ID"] if pd.notna(row["CAT_ID"]) else None,
                                    "partida_fc": row["PARTIDA_FC"] if row["PARTIDA_FC"] != "Sin categorizar" else None,
                                }
                            )

                        try:
                            # Insertar en lotes de 50 para evitar timeouts
                            total = len(registros)
                            importados = 0
                            for i in range(0, total, 50):
                                lote = registros[i : i + 50]
                                guardar_movimientos_lote(lote)
                                importados += len(lote)

                            st.success(f"🎉 ¡{importados} movimientos importados exitosamente!")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al importar: {e}")
                else:
                    st.warning("No hay movimientos válidos para importar. Revisa los errores arriba.")

    # ── PESTAÑA: HISTORIAL DE MOVIMIENTOS ──
    with (tab_historial if es_admin else tab_historial):
        if not es_admin:
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
# 10. PÁGINA: DASHBOARD
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
# 11. PÁGINA: CONCILIACIÓN BANCARIA
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
# 12. FOOTER
# ──────────────────────────────────────────────
st.divider()
st.caption("Flujo de Caja Dashboard v2.0 — Desarrollado para @contabilidad_22")
