from datetime import date
import pandas as pd
from streamlit.testing.v1 import AppTest

def nueva():
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at

# ---- 1) presupuesto sencillo ----
at = nueva()
at.session_state["nombre"] = "Raquel García"
at.session_state["telefono"] = "+34 644 97 37 21"
at.session_state["localidad"] = "Valencia"
at.session_state["importe_unico"] = 350.0
at.session_state["fecha"] = date(2026, 10, 16)
at.run()
assert not at.exception, at.exception
btn = [b for b in at.button if "Generar" in b.label][0]
assert not btn.disabled, [w.value for w in at.warning]
btn.click().run()
assert not at.exception, at.exception
h = at.session_state["historial"]
print("1) generado:", list(h))
n = list(h)[0]
assert n == "20261016_644973721_RG", n
assert h[n]["pdf"][:4] == b"%PDF"
print("   fichero:", h[n]["fichero"], "| total:", h[n]["total"])

# ---- 2) desglosado con descuento ----
at = nueva()
at.session_state["nombre"] = "Luis Cano Patón"
at.session_state["telefono"] = "615 13 91 91"
at.session_state["localidad"] = "Valencia"
at.session_state["calle"] = "C/ República Costa de Marfil, 8"
at.session_state["modo"] = "Desglosar por partidas"
at.session_state["partidas"] = pd.DataFrame({
    "Concepto": ["Balcón · 3,50 x 1,80 m", "Ventana comedor", "Ventana cocina", ""],
    "Importe (€)": [400.0, 80.0, 60.0, None]})
at.session_state["dto_tipo"] = "Importe fijo (€)"
at.session_state["dto_valor"] = 40.0
at.run()
assert not at.exception, at.exception
[b for b in at.button if "Generar" in b.label][0].click().run()
assert not at.exception, at.exception
h = at.session_state["historial"]
n = list(h)[0]
print("2) generado:", n, "| total:", h[n]["total"])
assert abs(h[n]["total"] - 500.0) < 0.01

# ---- 3) total deseado mayor que las partidas «incluido» ----
at = nueva()
at.session_state["nombre"] = "Alex"
at.session_state["telefono"] = "667 57 22 72"
at.session_state["localidad"] = "Gorga (Alicante)"
at.session_state["modo"] = "Desglosar por partidas"
at.session_state["partidas"] = pd.DataFrame({
    "Concepto": ["Red barbacoa-techado", "Cerramiento parcial", "Desplazamiento"],
    "Importe (€)": [None, None, 150.0]})
at.session_state["total_deseado"] = 650.0
at.run()
[b for b in at.button if "Generar" in b.label][0].click().run()
assert not at.exception, at.exception
h = at.session_state["historial"]; n = list(h)[0]
print("3) generado:", n, "| total:", h[n]["total"])
assert abs(h[n]["total"] - 650.0) < 0.01

# ---- 4) validación: sin nombre el botón está bloqueado ----
at = nueva()
at.session_state["importe_unico"] = 100.0
at.run()
btn = [b for b in at.button if "Generar" in b.label][0]
assert btn.disabled
print("4) sin nombre/teléfono el botón está desactivado: OK")
print("TODO OK")
