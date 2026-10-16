"""
Generador del PDF de presupuesto · TOP REDES VALENCIA (SOS Madera, S.L.)

Port a Python (reportlab) del generador jsPDF original, con las mismas
medidas (mm, origen arriba-izquierda), colores y tipografías.
"""
import io
import math
import os

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(AQUI, "assets", "logo.png")
GATO = os.path.join(AQUI, "assets", "gato.jpg")

W, H, M = 210.0, 297.0, 16.0

PAL = {
    "magenta": (200, 30, 134),
    "magentaD": (158, 15, 104),
    "pinkL": (249, 220, 238),
    "pinkXL": (253, 242, 248),
    "ink": (58, 31, 49),
    "grey": (107, 84, 98),
    "dotted": (201, 168, 188),
    "penVal": (40, 58, 116),
    "net": (251, 239, 247),
    "band": (252, 243, 249),
    "stampInk": (205, 125, 174),
}

FUENTES = {
    "normal": "Helvetica",
    "bold": "Helvetica-Bold",
    "italic": "Helvetica-Oblique",
    "bolditalic": "Helvetica-BoldOblique",
    "courier": "Courier-Bold",
}


def _san(t):
    """deja solo caracteres que la fuente estándar (WinAnsi) puede pintar"""
    import unicodedata
    out = []
    for ch in str(t):
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            base = unicodedata.normalize("NFKD", ch)
            base = "".join(c for c in base if not unicodedata.combining(c))
            try:
                base.encode("cp1252")
                out.append(base)
            except UnicodeEncodeError:
                out.append("?")
    return "".join(out)


def eur(v):
    """1234.5 -> '1.234,50 €'"""
    p = "%.2f" % v
    ent, dec = p.split(".")
    partes = []
    while len(ent) > 3:
        partes.insert(0, ent[-3:])
        ent = ent[:-3]
    partes.insert(0, ent)
    return ".".join(partes) + "," + dec + " \u20ac"


class _Pdf:
    """Pequeña capa sobre reportlab con coordenadas en mm desde arriba."""

    def __init__(self):
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=(W * mm, H * mm))
        self.c.setLineJoin(1)
        self.c.setLineCap(1)
        self.font = "Helvetica"
        self.size = 10

    # --- estado ---
    def fill(self, col):
        self.c.setFillColorRGB(*(v / 255.0 for v in col))

    def stroke(self, col):
        self.c.setStrokeColorRGB(*(v / 255.0 for v in col))

    def lw(self, pt):
        self.c.setLineWidth(pt)

    def dash(self, activo):
        if activo:
            self.c.setDash([0.5 * mm, 0.64 * mm], 0)
        else:
            self.c.setDash([], 0)

    def f(self, estilo, size):
        self.font = FUENTES[estilo]
        self.size = size
        self.c.setFont(self.font, size)

    def tw(self, txt):
        """ancho del texto en mm con la fuente actual"""
        return stringWidth(_san(txt), self.font, self.size) / mm

    # --- primitivas ---
    def text(self, txt, x, y, align="left"):
        txt = _san(txt)
        X, Yy = x * mm, (H - y) * mm
        if align == "right":
            self.c.drawRightString(X, Yy, txt)
        elif align == "center":
            self.c.drawCentredString(X, Yy, txt)
        else:
            self.c.drawString(X, Yy, txt)

    def line(self, x1, y1, x2, y2):
        self.c.line(x1 * mm, (H - y1) * mm, x2 * mm, (H - y2) * mm)

    def rect(self, x, y, w, h, relleno=True):
        self.c.rect(x * mm, (H - y - h) * mm, w * mm, h * mm,
                    stroke=0 if relleno else 1, fill=1 if relleno else 0)

    def rrect(self, x, y, w, h, r, modo="F"):
        self.c.roundRect(x * mm, (H - y - h) * mm, w * mm, h * mm, r * mm,
                         stroke=1 if "D" in modo else 0, fill=1 if "F" in modo else 0)

    def circle(self, cx, cy, r):
        self.c.circle(cx * mm, (H - cy) * mm, r * mm, stroke=1, fill=0)

    def texto_girado(self, txt, x, y, grados):
        """
        Texto girado 'grados' (antihorario) con la misma colocación que el
        generador original (jsPDF, align=center, baseline=middle):
        el centrado y la línea base se calculan SIN girar y después el texto
        rota alrededor de su punto de inicio. Por eso el cuño queda como en
        los presupuestos de siempre.
        """
        c = self.c
        txt = _san(txt)
        w_pt = stringWidth(txt, self.font, self.size)
        c.saveState()
        c.translate(x * mm - w_pt / 2.0, (H - y) * mm - self.size * K_MEDIO)
        c.rotate(grados)
        c.drawString(0, 0, txt)
        c.restoreState()

    def envolver(self, txt, ancho_mm):
        """equivalente a splitTextToSize: reparte en líneas por palabras"""
        lineas, actual = [], ""
        for palabra in txt.split(" "):
            prueba = palabra if not actual else actual + " " + palabra
            if self.tw(prueba) <= ancho_mm or not actual:
                actual = prueba
            else:
                lineas.append(actual)
                actual = palabra
        if actual:
            lineas.append(actual)
        return lineas


# desplazamiento vertical para "baseline: middle" (fracción del tamaño de letra)
K_MEDIO = 0.347


# ---------------------------------------------------------------------------
def generar_pdf(d):
    """
    d admite:
      numero, nombre, telefono, dni, direccion, concepto, detalle, fecha
      lineas: [{"c": texto, "i": importe | None, "t": "incluido" | None}]
      descuentoEur, descuentoPct, descuentoEtq
      importe  (float)  total sin IVA
      iva: "no" | "si" | None ; ivaPct ; notaGrande
      garantia: "12" | "36" ; clausulaAnclajes ; metodosPago ; cuno
    Devuelve los bytes del PDF.
    """
    p = _Pdf()
    p.f("normal", 10)

    # ---------- trama de red de fondo ----------
    p.stroke(PAL["net"])
    p.lw(0.6)
    paso = 11
    for i in range(-30, 30):
        p.line(i * paso, H, i * paso + H, 0)
        p.line(i * paso, H, i * paso - H, 0)

    # ---------- banda superior ----------
    p.fill(PAL["band"])
    p.rect(0, 0, W, 46)

    # ---------- cabecera ----------
    p.c.drawImage(LOGO, M * mm, (H - 12 - 24) * mm, 24 * mm, 24 * mm, mask="auto")
    tx = M + 24 + 6
    p.fill(PAL["magenta"])
    p.f("bold", 24)
    p.text("TOP REDES", tx, 23)
    p.fill(PAL["magentaD"])
    p.f("normal", 13.5)
    p.text("V A L E N C I A", tx + 1, 29.5)
    p.fill(PAL["grey"])
    p.f("normal", 8.6)
    p.text("Calle Paterna 8 bajo dcha, Betera  \u00b7  Tel. 683 597 759", tx, 34.5)

    p.stroke(PAL["magenta"]); p.lw(1.6); p.line(M, 41, W - M, 41)
    p.stroke(PAL["pinkL"]);   p.lw(0.9); p.line(M, 42.8, W - M, 42.8)

    # ---------- responsable ----------
    p.fill(PAL["grey"])
    p.f("normal", 8.4)
    resp = p.envolver(
        "Responsable de la instalaci\u00f3n: SOS Madera, S.L., que cumple con los "
        "correspondientes seguros de responsabilidad civil y con la normativa vigente "
        "en Espa\u00f1a.", W - 2 * M)
    for i, ln in enumerate(resp):
        p.text(ln, M, 51 + i * 3.88)

    # ---------- título ----------
    p.fill(PAL["magenta"])
    p.rrect(M, 63.76, W - 2 * M, 20, 3)
    p.fill((255, 255, 255))
    p.f("bold", 16.5)
    p.text("PRESUPUESTO DE INSTALACI\u00d3N", W / 2, 73.2, "center")
    p.f("courier", 9.6)
    if d.get("numero"):
        p.text("N.\u00ba " + d["numero"], W / 2, 80.2, "center")
    else:
        et = "N.\u00ba "
        ew, linea_w = p.tw(et), 52
        x0 = W / 2 - (ew + linea_w) / 2
        p.text(et, x0, 80.2)
        p.stroke((255, 255, 255)); p.lw(0.7); p.dash(True)
        p.line(x0 + ew, 81.1, x0 + ew + linea_w, 81.1)
        p.dash(False)

    # ---------- datos del cliente ----------
    p.fill(PAL["magenta"])
    p.f("bold", 11)
    p.text("DATOS DEL CLIENTE", M, 91.76)
    p.stroke(PAL["pinkL"]); p.lw(1.2); p.line(M, 94.16, W - M, 94.16)

    def campo(yb, label, valor, wmax=None, x0=None):
        xi = M if x0 is None else x0
        p.fill(PAL["ink"])
        p.f("normal", 10)
        p.text(label, xi, yb)
        lw_ = p.tw(label)
        x1 = xi + lw_ + 2
        x2 = xi + (wmax if wmax else (W - M - xi))
        p.stroke(PAL["dotted"]); p.lw(0.7); p.dash(True)
        p.line(x1, yb + 0.8, x2, yb + 0.8)
        p.dash(False)
        if valor:
            p.fill(PAL["penVal"])
            s = 10.0
            p.f("bold", s)
            while p.tw(valor) > x2 - (M + lw_ + 4) - 1 and s > 6.4:
                s -= 0.2
                p.f("bold", s)
            p.text(valor, xi + lw_ + 4, yb - 0.4)
            p.fill(PAL["ink"])

    nombre, tel = d.get("nombre", ""), d.get("telefono", "")
    if d.get("dni") or d.get("direccion"):
        grupos = [[("Nombre y apellidos:", nombre, None, None)]]
        grupos.append([("DNI/NIF:", d.get("dni", ""), 46, M),
                       ("Tel\u00e9fono:", tel, None, M + 62)])
        if d.get("direccion"):
            grupos.append([("Direcci\u00f3n:", d["direccion"], None, None)])
        if d.get("concepto"):
            grupos.append([("Concepto:", d["concepto"], None, None)])
        if d.get("detalle"):
            grupos.append([("Detalle:", d["detalle"], None, None)])
        pasoy = 7 if len(grupos) >= 5 else 8
        y0 = 131.76 - 4 - (len(grupos) - 1) * pasoy
        for i, g in enumerate(grupos):
            for lab, val, wm, xx in g:
                campo(y0 + i * pasoy, lab, val, wm, xx)
    elif d.get("detalle"):
        campo(100.5, "Nombre y apellidos:", nombre)
        campo(108.5, "Tel\u00e9fono:", tel, (W - 2 * M) * 0.55)
        campo(116.5, "Concepto:", d.get("concepto", ""))
        campo(124.5, "Detalle:", d["detalle"])
    else:
        campo(101.76, "Nombre y apellidos:", nombre)
        campo(110.76, "Tel\u00e9fono:", tel, (W - 2 * M) * 0.55)
        campo(119.76, "Concepto:", d.get("concepto", ""))

    # ---------- ilustración o tabla de partidas ----------
    lineas = d.get("lineas") or None
    if lineas:
        x1, x2 = M, W - M
        dto_eur = d.get("descuentoEur") or 0
        dto_pct = d.get("descuentoPct") or 0
        hay_dto = bool(dto_eur or dto_pct)
        n_filas = 1 + len(lineas) + (2 if hay_dto else 0)
        y_tope, y_zona = 179.0, 134.0
        alto = min(7.0, (y_tope - y_zona) / max(n_filas - 1, 1))
        usado = (n_filas - 1) * alto
        yy = max(y_zona + 1.5, y_zona + (y_tope - y_zona - usado) / 2)
        p.fill(PAL["magenta"])
        p.rect(x1, yy - alto + 1.8, x2 - x1, alto)
        p.fill((255, 255, 255))
        fs = 10 if alto >= 6.4 else (9 if alto >= 5.6 else 8)
        p.f("bold", min(8.8, fs))
        p.text("CONCEPTO", x1 + 4, yy)
        p.text("IMPORTE", x2 - 4, yy, "right")
        yy += alto
        suma = 0.0
        for i, ln in enumerate(lineas):
            if i % 2 == 1:
                p.fill(PAL["pinkXL"])
                p.rect(x1, yy - alto + 1.8, x2 - x1, alto)
            p.fill(PAL["ink"])
            p.f("normal", 9 if alto < 7 else 10)
            p.text(str(ln["c"]), x1 + 4, yy)
            p.f("bold", 9 if alto < 7 else 10)
            p.text(ln.get("t") or eur(ln.get("i") or 0), x2 - 4, yy, "right")
            suma += ln.get("i") or 0
            yy += alto
        p.stroke(PAL["pinkL"]); p.lw(1)
        p.line(x1, yy - 5, x2, yy - 5)
        dto = dto_eur if dto_eur else (suma * dto_pct / 100.0 if dto_pct else 0)
        if dto > 0:
            p.fill(PAL["grey"])
            p.f("normal", min(9.6, fs))
            p.text("Subtotal", x1 + 4, yy)
            p.text(eur(suma), x2 - 4, yy, "right")
            yy += alto
            if d.get("descuentoEtq"):
                etiq = d["descuentoEtq"]
            elif dto_pct:
                etiq = "Descuento por acumulaci\u00f3n de instalaciones (%g %%)" % dto_pct
            else:
                etiq = "Descuento por acumulaci\u00f3n de instalaciones"
            p.fill(PAL["magenta"])
            p.f("bold", min(9.6, fs))
            p.text(etiq, x1 + 4, yy)
            p.text("- " + eur(dto), x2 - 4, yy, "right")
            yy += alto
        p.stroke(PAL["magenta"]); p.lw(1.2)
        p.line(x1, yy - 5, x2, yy - 5)
    else:
        p.c.drawImage(GATO, 74 * mm, (H - 131.76 - 44.131) * mm, 62 * mm, 44.131 * mm)

    # ---------- lema ----------
    p.fill(PAL["ink"])
    l1a, l1b = "En ", "TOP REDES"
    l1c = ", ver tu hogar seguro es la mayor satisfacci\u00f3n de nuestro d\u00eda a d\u00eda."
    p.f("bold", 11);   wb = p.tw(l1b)
    p.f("normal", 11); wa, wc = p.tw(l1a), p.tw(l1c)
    cx = W / 2 - (wa + wb + wc) / 2
    p.f("normal", 11); p.text(l1a, cx, 185); cx += wa
    p.f("bold", 11);   p.text(l1b, cx, 185); cx += wb
    p.f("normal", 11); p.text(l1c, cx, 185)
    p.fill(PAL["magenta"])
    p.f("bold", 11)
    p.text("\u00a1Tu tranquilidad es nuestra recompensa!", W / 2, 190.5, "center")

    # ---------- garantía ----------
    con_clausula = d.get("clausulaAnclajes", True) is not False
    gh = 17 if con_clausula else 12
    p.fill(PAL["pinkXL"])
    p.rrect(M, 199.83, W - 2 * M, gh, 3)
    p.fill(PAL["magenta"])
    p.rrect(M, 199.83, 2.2, gh, 1.1)
    p.f("bold", 9.4)
    p.fill(PAL["magenta"])
    meses36 = str(d.get("garantia", "12")) == "36"
    cab = "GARANT\u00cdA DE 3 A\u00d1OS." if meses36 else "GARANT\u00cdA DE 12 MESES."
    p.text(cab, 24, 206.4 if con_clausula else 207.2)
    wcab = p.tw(cab)
    p.fill(PAL["ink"])
    p.f("normal", 9.4)
    if con_clausula:
        gtxt = ("La instalaci\u00f3n tiene una garant\u00eda de " +
                ("3 a\u00f1os" if meses36 else "12 meses") +
                ", salvo en los anclajes, que dependen del tipo de ladrillo o muro "
                "al que est\u00e1n sujetos.")
        gl = p.envolver(gtxt, W - 2 * M - 14 - wcab - 1.5)
        p.text(gl[0], 24 + wcab + 1.5, 206.4)
        resto = p.envolver(" ".join(gl[1:]), W - 2 * M - 14) if len(gl) > 1 else []
        for i, ln in enumerate(resto):
            p.text(ln, 24, 211 + i * 4.59)

    # ---------- bloque protectoras ----------
    p.c.drawImage(LOGO, M * mm, (H - 227 - 15) * mm, 15 * mm, 15 * mm, mask="auto")
    p.fill(PAL["magentaD"])
    p.f("bold", 9.2)
    p.text("COLABORAMOS CON ASOCIACIONES", M + 19, 232.69)
    p.text("PROTECTORAS DE ANIMALES", M + 19, 237.1)

    # ---------- detalles del presupuesto ----------
    col_x = 107.0
    col_w = W - M - col_x
    con_pagos = d.get("metodosPago", True) is not False
    box_h = 52 if con_pagos else 39
    p.stroke(PAL["magenta"]); p.lw(1.2)
    p.fill((255, 255, 255))
    p.rrect(col_x, 227, col_w, box_h, 3, "FD")
    p.fill(PAL["magenta"])
    p.rrect(col_x, 227, col_w, 9, 3)
    p.rect(col_x, 233, col_w, 3)
    p.fill((255, 255, 255))
    p.f("bold", 10.5)
    p.text("DETALLES DEL PRESUPUESTO", col_x + col_w / 2, 233.2, "center")

    p.fill(PAL["ink"])
    p.f("bold", 11)
    etq = "IMPORTE TOTAL:"
    p.text(etq, col_x + 5, 244)
    etq_w = p.tw(etq)
    total = d.get("importe")
    if total is not None:
        p.fill(PAL["magenta"])
        p.f("bold", 15)
        p.text(eur(total), W - M - 5, 244.6, "right")
        iva = d.get("iva")
        if iva:
            no_iva = (iva == "no")
            nota = "IVA NO incluido" if no_iva else "IVA incluido"
            if no_iva and d.get("ivaPct"):
                nota = "+ IVA %g %%  \u00b7  Total %s" % (
                    d["ivaPct"], eur(total * (1 + d["ivaPct"] / 100.0)))
            p.fill(PAL["magentaD"] if no_iva else PAL["grey"])
            ns = 11.5 if d.get("notaGrande") else 7.6
            p.f("bolditalic" if no_iva else "italic", ns)
            p.text(nota, W - M - 5, 251 if d.get("notaGrande") else 249.6, "right")
    else:
        p.stroke(PAL["dotted"]); p.lw(0.7); p.dash(True)
        p.line(col_x + 5 + etq_w + 3, 244.8, W - M - 10, 244.8)
        p.dash(False)
        p.fill(PAL["magenta"])
        p.f("bold", 11)
        p.text("\u20ac", W - M - 4, 244, "right")

    # fecha
    yb = 255.5
    p.fill(PAL["ink"])
    p.f("normal", 9.6)
    p.text("Fecha:", col_x + 5, yb)
    lw_ = p.tw("Fecha:")
    p.stroke(PAL["dotted"]); p.lw(0.7); p.dash(True)
    p.line(col_x + 5 + lw_ + 2, yb + 0.8, W - M - 5, yb + 0.8)
    p.dash(False)
    if d.get("fecha"):
        p.fill(PAL["penVal"])
        p.f("bold", 9.6)
        p.text(d["fecha"], col_x + 5 + lw_ + 4, yb - 0.4)

    # validez
    p.fill(PAL["magentaD"])
    p.f("bolditalic", 7)
    p.text("Presupuesto v\u00e1lido durante 30 d\u00edas desde esta fecha.", col_x + 5, 260)

    # métodos de pago
    if con_pagos:
        p.stroke(PAL["pinkL"]); p.lw(1)
        p.line(col_x + 5, 263.5, W - M - 5, 263.5)
        p.fill(PAL["magenta"])
        p.f("bold", 7.2)
        p.text("M\u00c9TODOS DE PAGO", col_x + 5, 267.5)
        p.fill(PAL["ink"])
        p.f("normal", 8)
        p.text("Efectivo o tarjeta", col_x + 5, 272)
        p.fill(PAL["grey"])
        p.f("italic", 6.5)
        p.text("El pago se realiza el d\u00eda de la instalaci\u00f3n.", col_x + 5, 276)

    # ---------- cuño ----------
    if d.get("cuno", True):
        _cuno(p, M + 45, 297 - 35, 16.5, -11)

    # ---------- pie ----------
    p.stroke(PAL["pinkL"]); p.lw(1.2); p.line(M, 283, W - M, 283)
    p.fill(PAL["magenta"])
    p.f("bold", 8.6)
    p.text("topredesvalencia.com", M, 287)
    p.fill(PAL["grey"])
    p.f("normal", 8.6)
    p.text("Redes de seguridad para gatos  \u00b7  Tel. 683 597 759", W - M, 287, "right")

    p.c.showPage()
    p.c.save()
    return p.buf.getvalue()


# ---------------------------------------------------------------------------
def _cuno(p, cx, cy, rad, giro):
    """cuño circular de SOS Madera (vectorial)"""
    p.stroke(PAL["stampInk"])
    p.fill(PAL["stampInk"])
    p.lw(1.5);  p.circle(cx, cy, rad)
    p.lw(0.7);  p.circle(cx, cy, rad - 1.5)
    p.lw(0.6);  p.circle(cx, cy, rad - 5.5)

    def rot(dx, dy):
        a = giro * math.pi / 180
        return (cx + dx * math.cos(a) - dy * math.sin(a),
                cy - dx * math.sin(a) - dy * math.cos(a))

    def anillo(r, txt, size, arriba):
        n = len(txt)
        span = min(155, 8.6 * n) * math.pi / 180
        start = math.pi / 2 + span / 2 if arriba else -math.pi / 2 - span / 2
        paso = (-1 if arriba else 1) * span / max(n - 1, 1)
        p.f("bold", size)
        for i, ch in enumerate(txt):
            ang = start + paso * i
            px, py = rot(r * math.cos(ang), r * math.sin(ang))
            grados = ang * 180 / math.pi + (-90 if arriba else 90) + giro
            p.texto_girado(ch, px, py, grados)

    anillo(rad - 3.3, "SOS MADERA, S.L.", 5.8, True)
    anillo(rad - 3.5, "BETERA \u00b7 VALENCIA", 5.0, False)

    def lin(dx, dy, txt, size, estilo):
        px, py = rot(dx, dy)
        p.f(estilo, size)
        p.texto_girado(txt, px, py, giro)

    lin(0, 2.6, "TOP REDES", 7.6, "bold")
    lin(0, 0.6, "V A L E N C I A", 5.0, "bold")
    s1, s2 = rot(-rad + 7.5, -0.9), rot(rad - 7.5, -0.9)
    p.lw(0.5)
    p.line(s1[0], s1[1], s2[0], s2[1])
    lin(0, -3.2, "Tel. 683 597 759", 5.2, "normal")
    lin(0, -5.5, "topredesvalencia.com", 4.8, "normal")
