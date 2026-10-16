"""
Presupuestos · TOP REDES VALENCIA
App de Streamlit: se añaden los datos y se genera el PDF del presupuesto.
"""
import csv
import io
import os
import re
import zipfile
from datetime import date

import pandas as pd
import pymupdf
import streamlit as st

from generador_pdf import _Pdf, eur, generar_pdf

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(AQUI, "assets", "logo.png")

st.set_page_config(page_title="Presupuestos · Top Redes Valencia",
                   page_icon=LOGO, layout="wide")

MAG = "#C81E86"
st.markdown(f"""
<style>
  h1, h2, h3 {{ color: {MAG}; }}
  div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] {{
      background-color: {MAG}; border-color: {MAG};
  }}
  div[data-testid="stMetricValue"] {{ color: {MAG}; }}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Acceso opcional con contraseña (Settings > Secrets:  APP_PASSWORD = "...")
# --------------------------------------------------------------------------
def _clave_configurada():
    try:
        return st.secrets["APP_PASSWORD"] if "APP_PASSWORD" in st.secrets else None
    except Exception:          # no hay fichero de secretos: acceso libre
        return None


CLAVE = _clave_configurada()
if CLAVE:
    if not st.session_state.get("acceso"):
        st.title("Presupuestos · Top Redes Valencia")
        clave = st.text_input("Contraseña", type="password")
        if clave:
            if clave == CLAVE:
                st.session_state["acceso"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        st.stop()

# --------------------------------------------------------------------------
# Valores por defecto del formulario
# --------------------------------------------------------------------------
PARTIDAS_VACIAS = pd.DataFrame({"Concepto": ["", ""], "Importe (€)": [None, None]})

DEFECTOS = {
    "nombre": "", "telefono": "", "dni": "", "calle": "", "localidad": "",
    "concepto": "Instalación de red de seguridad", "detalle": "",
    "modo": "Un solo importe", "importe_unico": 0.0,
    "dto_tipo": "Sin descuento", "dto_valor": 0.0, "dto_etq": "", "total_deseado": 0.0,
    "iva_modo": "IVA NO incluido (+ tipo)", "iva_pct": 10, "nota_grande": False,
    "fecha": date.today(), "numero_manual": "", "sufijo": "",
    "garantia": "12 meses", "clausula": True, "pagos": True, "cuno": True,
}

for k, v in DEFECTOS.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("partidas", PARTIDAS_VACIAS.copy())
st.session_state.setdefault("editor_ver", 0)
st.session_state.setdefault("historial", {})   # numero -> dict
st.session_state.setdefault("ultimo", None)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def solo_digitos(t):
    return re.sub(r"\D", "", t or "")


def telefono_9(t):
    d = solo_digitos(t)
    if len(d) > 9 and d.startswith("34"):
        d = d[2:]
    elif len(d) > 9 and d.startswith("0034"):
        d = d[4:]
    return d


def telefono_bonito(t):
    d = telefono_9(t)
    if len(d) == 9:
        return f"{d[:3]} {d[3:5]} {d[5:7]} {d[7:]}"
    return (t or "").strip()


PARTICULAS = {"de", "del", "la", "las", "los", "el", "y", "da", "di"}


def iniciales(nombre):
    pal = [p for p in re.split(r"\s+", (nombre or "").strip()) if p]
    letras = [p[0] for p in pal if p.lower() not in PARTICULAS] or [p[0] for p in pal]
    quitar = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")
    return "".join(letras).translate(quitar).upper()


def numero_auto():
    ss = st.session_state
    tel = telefono_9(ss["telefono"]) or "000000000"
    return f"{ss['fecha']:%Y%m%d}_{tel}_{iniciales(ss['nombre']) or 'X'}"


def lineas_validas():
    """partidas del editor -> lista para el generador"""
    df = st.session_state["partidas"]
    out = []
    for _, r in df.iterrows():
        c = str(r.get("Concepto") or "").strip()
        if not c:
            continue
        imp = r.get("Importe (€)")
        if pd.isna(imp) or imp is None or imp == "":
            out.append({"c": c, "t": "incluido"})
        else:
            out.append({"c": c, "i": float(imp)})
    return out


def calcular():
    """devuelve (lineas, subtotal, descuento_eur, total)"""
    ss = st.session_state
    if ss["modo"] == "Un solo importe":
        t = float(ss["importe_unico"] or 0)
        return [], t, 0.0, t
    lineas = lineas_validas()
    sub = sum(l.get("i", 0) for l in lineas)
    td = float(ss["total_deseado"] or 0)
    if td > sub:
        return lineas, sub, 0.0, td          # p.ej. partidas «incluido» + total fijo
    if 0 < td < sub:
        dto = sub - td
    elif ss["dto_tipo"] == "Importe fijo (€)":
        dto = float(ss["dto_valor"] or 0)
    elif ss["dto_tipo"] == "Porcentaje (%)":
        dto = round(sub * float(ss["dto_valor"] or 0) / 100.0, 2)
    else:
        dto = 0.0
    return lineas, sub, dto, sub - dto


def datos_pdf(numero):
    ss = st.session_state
    lineas, sub, dto, total = calcular()
    calle, loc = ss["calle"].strip(), ss["localidad"].strip()
    direccion = "  \u00b7  ".join(x for x in (calle, loc) if x)
    d = {
        "numero": numero,
        "nombre": ss["nombre"].strip(),
        "telefono": telefono_bonito(ss["telefono"]),
        "dni": ss["dni"].strip(),
        "direccion": direccion,
        "concepto": ss["concepto"].strip(),
        "detalle": ss["detalle"].strip(),
        "importe": total,
        "fecha": f"{ss['fecha']:%d/%m/%Y}",
        "garantia": "36" if ss["garantia"].startswith("3") else "12",
        "clausulaAnclajes": ss["clausula"],
        "metodosPago": ss["pagos"],
        "cuno": ss["cuno"],
    }
    if ss["iva_modo"].startswith("IVA NO"):
        d["iva"], d["ivaPct"] = "no", ss["iva_pct"]
    elif ss["iva_modo"].startswith("IVA incluido"):
        d["iva"] = "si"
    d["notaGrande"] = ss["nota_grande"]
    if ss["modo"] != "Un solo importe":
        d["lineas"] = lineas
        if dto > 0:
            d["descuentoEur"] = dto
            if ss["dto_etq"].strip():
                d["descuentoEtq"] = ss["dto_etq"].strip()
    return d


def ancho_mm(txt, estilo="bold", size=10):
    p = _Pdf()
    p.f(estilo, size)
    return p.tw(txt)


def png_vista_previa(pdf_bytes, dpi=110):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    return doc[0].get_pixmap(dpi=dpi).tobytes("png")


def cargar(numero):
    """vuelca un presupuesto del historial en el formulario"""
    h = st.session_state["historial"][numero]["form"]
    for k, v in h.items():
        if k == "partidas":
            st.session_state["partidas"] = v.copy()
            st.session_state["editor_ver"] += 1
        else:
            st.session_state[k] = v


def nuevo():
    for k, v in DEFECTOS.items():
        st.session_state[k] = v
    st.session_state["partidas"] = PARTIDAS_VACIAS.copy()
    st.session_state["editor_ver"] += 1
    st.session_state["ultimo"] = None


# --------------------------------------------------------------------------
# Cabecera
# --------------------------------------------------------------------------
c1, c2 = st.columns([1, 9])
c1.image(LOGO, width=80)
c2.title("Presupuestos · Top Redes Valencia")
c2.caption("Rellena los datos y genera el PDF del presupuesto.")

izq, der = st.columns([6, 5], gap="large")

# --------------------------------------------------------------------------
# FORMULARIO
# --------------------------------------------------------------------------
with izq:
    top = st.columns([1, 1])
    top[0].button("➕ Nuevo presupuesto", on_click=nuevo, width="stretch")
    if st.session_state["historial"]:
        elegido = top[1].selectbox(
            "Editar uno ya generado", [""] + list(st.session_state["historial"]),
            label_visibility="collapsed",
            format_func=lambda n: n or "Editar uno ya generado…")
        if elegido:
            st.button(f"Cargar {elegido} en el formulario", on_click=cargar, args=(elegido,))

    st.subheader("Cliente")
    a, b = st.columns(2)
    a.text_input("Nombre y apellidos *", key="nombre")
    b.text_input("Teléfono *", key="telefono", placeholder="612 34 56 78")
    a, b, c = st.columns([2, 2, 1.4])
    a.text_input("Calle y número (opcional)", key="calle")
    b.text_input("Localidad", key="localidad", placeholder="Valencia")
    c.text_input("DNI/NIF (opcional)", key="dni")

    st.subheader("Trabajo")
    st.text_input("Concepto", key="concepto")
    st.text_input("Detalle (opcional)", key="detalle",
                  placeholder="Balcón de 4 x 2,30 m, sobre muro…")
    for etiqueta, estilo, texto, limite in (
            ("Concepto", "bold", st.session_state["concepto"], 150),
            ("Detalle", "bold", st.session_state["detalle"], 150)):
        if texto and ancho_mm(texto, estilo, 10) > limite:
            st.warning(f"{etiqueta} muy largo: en el PDF se reducirá la letra y puede "
                       "no caber. Acórtalo o muévelo al campo contrario.")

    st.radio("Importe", ["Un solo importe", "Desglosar por partidas"],
             key="modo", horizontal=True)

    if st.session_state["modo"] == "Un solo importe":
        st.number_input("Importe sin IVA (€)", min_value=0.0, step=10.0, format="%.2f",
                        key="importe_unico")
    else:
        st.caption("Una fila por elemento. Si dejas el importe vacío, en el PDF "
                   "aparece «incluido».")
        editado = st.data_editor(
            st.session_state["partidas"], num_rows="dynamic", width="stretch",
            key=f"editor_{st.session_state['editor_ver']}",
            column_config={
                "Concepto": st.column_config.TextColumn(width="large"),
                "Importe (€)": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
            })
        st.session_state["partidas"] = editado

        st.radio("Descuento", ["Sin descuento", "Importe fijo (€)", "Porcentaje (%)"],
                 key="dto_tipo", horizontal=True)
        a, b = st.columns(2)
        if st.session_state["dto_tipo"] != "Sin descuento":
            a.number_input("Valor del descuento", min_value=0.0, step=5.0, key="dto_valor")
            b.text_input("Texto del descuento (opcional)", key="dto_etq",
                         placeholder="Descuento por acumulación de instalaciones")
        st.number_input("Total final deseado (opcional, 0 = automático)",
                        min_value=0.0, step=10.0, key="total_deseado",
                        help="Si es menor que la suma de partidas, el descuento se calcula "
                             "solo para llegar a este total. Si es mayor (p. ej. partidas "
                             "«incluido»), se usa tal cual como total.")

    st.subheader("IVA")
    a, b = st.columns([3, 1])
    a.radio("Nota bajo el importe",
            ["IVA NO incluido (+ tipo)", "IVA incluido", "Sin nota de IVA"],
            key="iva_modo", horizontal=True)
    if st.session_state["iva_modo"].startswith("IVA NO"):
        b.number_input("Tipo %", min_value=0, max_value=21, step=1, key="iva_pct")
    st.checkbox("Nota de IVA en letra grande (cliente con dificultad visual)",
                key="nota_grande")

    st.subheader("Documento")
    a, b, c = st.columns(3)
    a.date_input("Fecha", key="fecha", format="DD/MM/YYYY")
    b.selectbox("Garantía", ["12 meses", "3 años"], key="garantia")
    c.text_input("Sufijo del fichero", key="sufijo", placeholder="-v2, _A, _B…",
                 help="Sirve para distinguir versiones y evita que el móvil muestre "
                      "una versión antigua guardada en caché.")
    a, b, c = st.columns(3)
    a.checkbox("Cláusula de anclajes", key="clausula")
    b.checkbox("Métodos de pago", key="pagos")
    c.checkbox("Cuño de la empresa", key="cuno")
    st.text_input("Número de presupuesto", key="numero_manual",
                  placeholder=f"Automático: {numero_auto()}")

# --------------------------------------------------------------------------
# RESUMEN + GENERAR
# --------------------------------------------------------------------------
with der:
    lineas, sub, dto, total = calcular()
    st.subheader("Resumen")
    m = st.columns(3)
    if dto > 0:
        m[0].metric("Subtotal", eur(sub))
        m[1].metric("Descuento", "- " + eur(dto))
        m[2].metric("Total", eur(total))
    else:
        m[0].metric("Total sin IVA", eur(total))
        pct = st.session_state["iva_pct"] if st.session_state["iva_modo"].startswith("IVA NO") else 0
        m[1].metric(f"Con IVA {pct} %" if pct else "Con IVA", eur(total * (1 + pct / 100.0)))

    numero = st.session_state["numero_manual"].strip() or numero_auto()
    fichero = f"presupuesto-{numero}{st.session_state['sufijo'].strip()}.pdf"
    st.caption(f"Fichero: `{fichero}`")

    errores = []
    if not st.session_state["nombre"].strip():
        errores.append("Falta el nombre.")
    if len(telefono_9(st.session_state["telefono"])) != 9:
        errores.append("El teléfono debería tener 9 cifras.")
    if total <= 0:
        errores.append("El importe es cero.")
    if st.session_state["modo"] != "Un solo importe" and not lineas:
        errores.append("Añade al menos una partida.")
    for e in errores:
        st.warning(e)

    if st.button("📄 Generar PDF", type="primary", width="stretch",
                 disabled=bool(errores)):
        d = datos_pdf(numero)
        pdf = generar_pdf(d)
        guardado = {k: st.session_state[k] for k in DEFECTOS}
        guardado["partidas"] = st.session_state["partidas"].copy()
        st.session_state["historial"][numero] = {
            "form": guardado, "pdf": pdf, "fichero": fichero, "nombre": d["nombre"],
            "telefono": d["telefono"], "direccion": d["direccion"], "total": total,
            "fecha": d["fecha"], "detalle": d["detalle"] or d["concepto"],
            "valido": "",
        }
        st.session_state["ultimo"] = numero

    ult = st.session_state["ultimo"]
    if ult and ult in st.session_state["historial"]:
        h = st.session_state["historial"][ult]
        st.success(f"Generado: {h['fichero']}")
        st.download_button("⬇️ Descargar PDF", h["pdf"], file_name=h["fichero"],
                           mime="application/pdf", type="primary",
                           width="stretch")
        st.image(png_vista_previa(h["pdf"]), width="stretch")

# --------------------------------------------------------------------------
# HISTORIAL DE LA SESIÓN
# --------------------------------------------------------------------------
if st.session_state["historial"]:
    st.divider()
    st.subheader(f"Generados en esta sesión ({len(st.session_state['historial'])})")
    st.caption("⚠️ Streamlit Cloud no guarda ficheros: este historial dura mientras "
               "la pestaña siga abierta. Descarga el ZIP antes de cerrar.")
    filas = [{"Fecha": h["fecha"], "Nº": n, "Cliente": h["nombre"],
              "Teléfono": h["telefono"], "Localidad / dirección": h["direccion"],
              "Importe": h["total"], "Detalle": h["detalle"], "Fichero": h["fichero"]}
             for n, h in st.session_state["historial"].items()]
    st.dataframe(pd.DataFrame(filas), width="stretch", hide_index=True,
                 column_config={"Importe": st.column_config.NumberColumn(format="%.2f €")})

    bz = io.BytesIO()
    with zipfile.ZipFile(bz, "w", zipfile.ZIP_DEFLATED) as z:
        for h in st.session_state["historial"].values():
            z.writestr(h["fichero"], h["pdf"])
        s = io.StringIO()
        w = csv.writer(s, delimiter=";")
        w.writerow(["Fecha", "Nº presupuesto", "Cliente", "Teléfono", "Localidad",
                    "Importe", "Detalle", "Fichero"])
        for f in filas:
            w.writerow([f["Fecha"], f["Nº"], f["Cliente"], f["Teléfono"],
                        f["Localidad / dirección"], eur(f["Importe"]), f["Detalle"],
                        f["Fichero"]])
        z.writestr("INDICE.csv", "\ufeff" + s.getvalue())
    st.download_button("⬇️ Descargar todos (ZIP con PDF + índice)", bz.getvalue(),
                       file_name=f"presupuestos-{date.today():%Y%m%d}.zip",
                       mime="application/zip")
