"""
Memoria de cálculo: documento completo del diseño de un elemento.

Genera el documento en tres formatos:
    * HTML autocontenido (con figuras SVG incrustadas).
    * Markdown.
    * PDF (requiere reportlab; las figuras se incluyen si svglib está disponible).

La memoria sigue el orden habitual de una memoria estructural peruana:
datos → solicitaciones → criterios → diseño → verificaciones → conclusiones.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import math
import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from . import figuras, normas


# ===========================================================================
# Utilidades de formato
# ===========================================================================
def ff(x: float, dec: int = 2) -> str:
    """Formato numérico con separador de miles."""
    if x is None:
        return "—"
    try:
        return f"{x:,.{dec}f}"
    except (TypeError, ValueError):
        return str(x)


def tm(x_kgfcm: float, dec: int = 2) -> str:
    return ff(x_kgfcm / 1e5, dec)


def tf(x_kgf: float, dec: int = 2) -> str:
    return ff(x_kgf / 1e3, dec)


def cm2(x: float, dec: int = 2) -> str:
    return ff(x, dec)


def _si(v) -> str:
    return "CUMPLE" if v else "NO CUMPLE"


def _clase(v) -> str:
    return "ok" if v else "mal"


# ===========================================================================
# Documento
# ===========================================================================
@dataclass
class Bloque:
    tipo: str                    # h1/h2/h3/p/f/tabla/fig/nota/lista
    contenido: object
    meta: dict = field(default_factory=dict)


class Doc:
    def __init__(self, titulo: str, subtitulo: str = ""):
        self.titulo = titulo
        self.subtitulo = subtitulo
        self.bloques: List[Bloque] = []

    # --- constructores -------------------------------------------------
    def h1(self, t: str):
        self.bloques.append(Bloque("h1", t))

    def h2(self, t: str, numero: str = ""):
        self.bloques.append(Bloque("h2", t, {"numero": numero}))

    def h3(self, t: str):
        self.bloques.append(Bloque("h3", t))

    def p(self, t: str):
        self.bloques.append(Bloque("p", t))

    def formula(self, t: str, resultado: str = ""):
        self.bloques.append(Bloque("f", t, {"resultado": resultado}))

    def nota(self, t: str):
        self.bloques.append(Bloque("nota", t))

    def lista(self, items: Sequence[str]):
        self.bloques.append(Bloque("lista", list(items)))

    def tabla(self, cabecera: Sequence[str], filas: Sequence[Sequence],
              titulo: str = "", anchos: Optional[Sequence[str]] = None,
              alinear: str = "c"):
        self.bloques.append(Bloque("tabla", {"cabecera": list(cabecera),
                                             "filas": [list(f) for f in filas],
                                             "titulo": titulo,
                                             "anchos": anchos,
                                             "alinear": alinear}))

    def figura(self, svg: str, pie: str = ""):
        if svg:
            self.bloques.append(Bloque("fig", svg, {"pie": pie}))

    # --- render --------------------------------------------------------
    def html(self, encabezado_extra: str = "") -> str:
        css = """
        :root{--azul:#1f3864;--gris:#5b6778;--linea:#d7dee8;--ok:#1f6f43;--mal:#c00000;}
        *{box-sizing:border-box}
        body{font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#1b2430;
             margin:0;background:#eef1f5;line-height:1.5;}
        .hoja{max-width:960px;margin:0 auto;background:#fff;padding:46px 54px;
              box-shadow:0 2px 14px rgba(0,0,0,.08);}
        .portada{border-bottom:4px solid var(--azul);padding-bottom:18px;margin-bottom:26px;}
        .portada h1{font-size:26px;margin:0 0 6px;color:var(--azul);letter-spacing:.2px}
        .portada .sub{color:var(--gris);font-size:14px}
        .kpis{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 26px}
        .kpi{flex:1 1 150px;border:1px solid var(--linea);border-left:4px solid var(--azul);
             padding:10px 12px;background:#f8fafc;border-radius:3px}
        .kpi b{display:block;font-size:18px;color:var(--azul)}
        .kpi span{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--gris)}
        h2{font-size:17px;color:var(--azul);margin:30px 0 8px;padding-bottom:4px;
           border-bottom:1px solid var(--linea)}
        h2 .num{display:inline-block;min-width:28px;color:#8fa3bd}
        h3{font-size:14px;color:#2c4a70;margin:20px 0 6px}
        p{margin:6px 0;font-size:13.5px;text-align:justify}
        ul{margin:6px 0 6px 20px;font-size:13.5px}
        table{border-collapse:collapse;width:100%;margin:10px 0 16px;font-size:12px}
        th{background:var(--azul);color:#fff;padding:7px 6px;font-weight:600;
           border:1px solid #17294a;text-align:center;font-size:11px}
        td{border:1px solid var(--linea);padding:5px 6px;text-align:center}
        tbody tr:nth-child(even){background:#f6f8fb}
        .titulo-tabla{font-size:12px;font-weight:600;color:var(--gris);margin:14px 0 2px}
        .formula{font-family:'Cambria Math','Consolas',monospace;background:#f5f7fa;
                 border-left:3px solid #9fb3cc;padding:8px 12px;margin:8px 0;font-size:13px;
                 white-space:pre-wrap}
        .formula b{color:var(--azul)}
        .nota{background:#fff8e6;border-left:3px solid #d9a300;padding:8px 12px;
              font-size:12.5px;margin:10px 0}
        .ok{color:var(--ok);font-weight:700}
        .mal{color:var(--mal);font-weight:700}
        .figura{margin:16px 0;text-align:center}
        .figura svg{max-width:100%;height:auto}
        .pie{font-size:11px;color:var(--gris);margin-top:2px}
        footer{margin-top:36px;border-top:1px solid var(--linea);padding-top:10px;
               font-size:11px;color:var(--gris);display:flex;justify-content:space-between}
        @media print{body{background:#fff}.hoja{box-shadow:none;padding:0}
                     h2{page-break-after:avoid}table{page-break-inside:avoid}}
        """
        out = ["<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>",
               f"<title>{_html.escape(self.titulo)}</title><style>{css}</style>",
               encabezado_extra, "</head><body><div class='hoja'>"]
        out.append("<div class='portada'>")
        out.append(f"<h1>{_html.escape(self.titulo)}</h1>")
        if self.subtitulo:
            out.append(f"<div class='sub'>{self.subtitulo}</div>")
        out.append("</div>")
        for b in self.bloques:
            out.append(self._html_bloque(b))
        out.append(f"<footer><span>{_html.escape(self.titulo)}</span>"
                   f"<span>{_dt.datetime.now():%d/%m/%Y %H:%M}</span></footer>")
        out.append("</div></body></html>")
        return "\n".join(out)

    def _html_bloque(self, b: Bloque) -> str:
        if b.tipo == "h1":
            return f"<h2>{_html.escape(str(b.contenido))}</h2>"
        if b.tipo == "h2":
            n = b.meta.get("numero", "")
            return (f"<h2><span class='num'>{_html.escape(n)}</span>"
                    f"{_html.escape(str(b.contenido))}</h2>")
        if b.tipo == "h3":
            return f"<h3>{_html.escape(str(b.contenido))}</h3>"
        if b.tipo == "p":
            return f"<p>{b.contenido}</p>"
        if b.tipo == "nota":
            return f"<div class='nota'>{b.contenido}</div>"
        if b.tipo == "f":
            res = b.meta.get("resultado")
            extra = f"\n<b>→ {_html.escape(res)}</b>" if res else ""
            return f"<div class='formula'>{_html.escape(str(b.contenido))}{extra}</div>"
        if b.tipo == "lista":
            return "<ul>" + "".join(f"<li>{x}</li>" for x in b.contenido) + "</ul>"
        if b.tipo == "fig":
            pie = f"<div class='pie'>{_html.escape(b.meta.get('pie',''))}</div>"
            return f"<div class='figura'>{b.contenido}{pie}</div>"
        if b.tipo == "tabla":
            c = b.contenido
            titulo = f"<div class='titulo-tabla'>{_html.escape(c['titulo'])}</div>" if c["titulo"] else ""
            cab = "".join(f"<th>{_html.escape(str(h))}</th>" for h in c["cabecera"])
            filas = []
            for fila in c["filas"]:
                celdas = []
                for celda in fila:
                    txt = str(celda)
                    clase = ""
                    if txt in ("CUMPLE", "SÍ", "SI", "OK"):
                        clase = " class='ok'"
                    elif txt in ("NO CUMPLE", "NO"):
                        clase = " class='mal'"
                    celdas.append(f"<td{clase}>{txt}</td>")
                filas.append("<tr>" + "".join(celdas) + "</tr>")
            return (f"{titulo}<table><thead><tr>{cab}</tr></thead><tbody>"
                    + "".join(filas) + "</tbody></table>")
        return ""

    # --- markdown ------------------------------------------------------
    def markdown(self) -> str:
        out = [f"# {self.titulo}", ""]
        if self.subtitulo:
            out += [f"*{self.subtitulo}*", ""]
        num = 0
        for b in self.bloques:
            if b.tipo == "h1":
                out += [f"## {b.contenido}", ""]
            elif b.tipo == "h2":
                num += 1
                out += [f"### {b.meta.get('numero','')} {b.contenido}".strip(), ""]
            elif b.tipo == "h3":
                out += [f"#### {b.contenido}", ""]
            elif b.tipo == "p":
                out += [str(b.contenido), ""]
            elif b.tipo == "nota":
                out += [f"> **Nota:** {b.contenido}", ""]
            elif b.tipo == "f":
                out += ["```", str(b.contenido)]
                if b.meta.get("resultado"):
                    out.append(f"→ {b.meta['resultado']}")
                out += ["```", ""]
            elif b.tipo == "lista":
                out += [f"- {x}" for x in b.contenido] + [""]
            elif b.tipo == "tabla":
                c = b.contenido
                if c["titulo"]:
                    out += [f"**{c['titulo']}**", ""]
                out.append("| " + " | ".join(str(h) for h in c["cabecera"]) + " |")
                out.append("|" + "|".join("---" for _ in c["cabecera"]) + "|")
                for fila in c["filas"]:
                    out.append("| " + " | ".join(str(x) for x in fila) + " |")
                out.append("")
            elif b.tipo == "fig":
                out += [f"*{b.meta.get('pie','[figura]')}*", ""]
        return "\n".join(out)

    # --- pdf -----------------------------------------------------------
    def pdf(self, ruta: str) -> bool:
        """Genera el PDF con reportlab. Devuelve False si no está disponible."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import cm
            from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                            SimpleDocTemplate, Spacer, Table, TableStyle)
        except ImportError:
            return False

        estilos = getSampleStyleSheet()
        azul = colors.HexColor("#1f3864")
        st_titulo = ParagraphStyle("t", parent=estilos["Title"], fontSize=20, textColor=azul,
                                   spaceAfter=6, alignment=TA_CENTER)
        st_sub = ParagraphStyle("s", parent=estilos["Normal"], fontSize=10,
                                textColor=colors.HexColor("#5b6778"), alignment=TA_CENTER)
        st_h1 = ParagraphStyle("h1", parent=estilos["Heading2"], fontSize=13, textColor=azul,
                               spaceBefore=14, spaceAfter=6)
        st_h2 = ParagraphStyle("h2", parent=estilos["Heading3"], fontSize=11.5,
                               textColor=colors.HexColor("#2c4a70"), spaceBefore=10, spaceAfter=4)
        st_p = ParagraphStyle("p", parent=estilos["Normal"], fontSize=9,
                              alignment=TA_JUSTIFY, spaceAfter=3, leading=12)
        st_f = ParagraphStyle("f", parent=estilos["Code"], fontSize=8, leading=10.5,
                              backColor=colors.HexColor("#f5f7fa"), borderPadding=4,
                              leftIndent=6, spaceBefore=3, spaceAfter=5)
        st_nota = ParagraphStyle("n", parent=st_p, fontSize=8.5,
                                 backColor=colors.HexColor("#fff8e6"), borderPadding=4,
                                 leftIndent=4, spaceAfter=6)
        st_pie = ParagraphStyle("pie", parent=estilos["Normal"], fontSize=7.5,
                                textColor=colors.HexColor("#5b6778"), alignment=TA_CENTER)

        doc = SimpleDocTemplate(ruta, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                                topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                                title=self.titulo)
        flujo = [Paragraph(_html.escape(self.titulo), st_titulo)]
        if self.subtitulo:
            flujo.append(Paragraph(_html.escape(self.subtitulo), st_sub))
        flujo.append(Spacer(1, 10))

        for b in self.bloques:
            if b.tipo in ("h1", "h2"):
                txt = str(b.contenido)
                if b.tipo == "h2" and b.meta.get("numero"):
                    txt = f"{b.meta['numero']} {txt}"
                flujo.append(Paragraph(_html.escape(txt), st_h1))
            elif b.tipo == "h3":
                flujo.append(Paragraph(_html.escape(str(b.contenido)), st_h2))
            elif b.tipo == "p":
                flujo.append(Paragraph(str(b.contenido), st_p))
            elif b.tipo == "nota":
                flujo.append(Paragraph(str(b.contenido), st_nota))
            elif b.tipo == "f":
                txt = _html.escape(str(b.contenido)).replace("\n", "<br/>")
                if b.meta.get("resultado"):
                    txt += f"<br/><b>→ {_html.escape(b.meta['resultado'])}</b>"
                flujo.append(Paragraph(txt, st_f))
            elif b.tipo == "lista":
                for x in b.contenido:
                    flujo.append(Paragraph(f"• {x}", st_p))
            elif b.tipo == "tabla":
                c = b.contenido
                datos = [[Paragraph(f"<b>{_html.escape(str(h))}</b>", st_p)
                          for h in c["cabecera"]]]
                for fila in c["filas"]:
                    datos.append([Paragraph(_html.escape(str(x)), st_p) for x in fila])
                anchos = c.get("anchos") or [None] * len(c["cabecera"])
                if any(anchos):
                    anchos = [a or "*" for a in anchos]
                t = Table(datos, colWidths=None, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), azul),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d3e0")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#f6f8fb")]),
                ]))
                if c["titulo"]:
                    flujo.append(Paragraph(f"<b>{_html.escape(c['titulo'])}</b>", st_p))
                flujo.append(t)
                flujo.append(Spacer(1, 6))
            elif b.tipo == "fig":
                img = _svg_a_png(b.contenido)
                if img:
                    ancho = 14 * cm
                    flujo.append(Image(img, width=ancho, height=ancho * 0.6, kind="proportional"))
                if b.meta.get("pie"):
                    flujo.append(Paragraph(_html.escape(b.meta["pie"]), st_pie))
                flujo.append(Spacer(1, 6))
        doc.build(flujo)
        return True


def _svg_a_png(svg: str):
    """Convierte SVG a una imagen para reportlab (requiere svglib)."""
    try:
        import os
        import tempfile
        from io import BytesIO
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        dibujo = svg2rlg(BytesIO(svg.encode("utf-8")))
        if dibujo is None:
            return None
        fd, ruta = tempfile.mkstemp(suffix=".png", prefix="e060_fig_")
        os.close(fd)
        renderPM.drawToFile(dibujo, ruta, fmt="PNG")
        return ruta
    except Exception:
        return None


# ===========================================================================
# Memoria de una viga
# ===========================================================================
def memoria_viga(salida: dict) -> Doc:
    el = salida["elemento"]
    opc = salida["opciones"]
    res = salida["resultado"]
    r = salida["resumen"]
    b, h, fc, fy, L = res["b"], res["h"], res["fc"], res["fy"], res["L"]
    rec, dbe = res["recubrimiento"], res["db_estribo"]
    d0 = res["d0"]
    sismico = res["sismico"]

    doc = Doc("MEMORIA DE CÁLCULO — VIGA DE CONCRETO ARMADO",
              f"Norma Técnica Peruana E.060 Concreto Armado · {el.nombre}")
    doc.nota(f"Documento generado el {salida['fecha']} por el sistema "
             f"<b>Diseño E.060 + ETABS</b>. Los resultados deben ser revisados y "
             f"validados por el ingeniero estructural responsable del proyecto.")

    # ---------------- 1. Datos ----------------
    doc.h2("Datos generales", "1.")
    doc.tabla(["Concepto", "Valor"], [
        ["Proyecto", opc.proyecto or "—"],
        ["Ubicación", opc.ubicacion or "—"],
        ["Elemento", f"{el.nombre} ({el.tipo})"],
        ["Nivel / Piso", el.story or "—"],
        ["Sección", f"{ff(b,0)} × {ff(h,0)} cm ({el.seccion or '—'})"],
        ["Luz / longitud", f"{ff(L/100,2)} m"],
        ["Fuente de solicitaciones", el.origen or "—"],
        ["Combinaciones analizadas", f"{len(el.combos)}"],
        ["Diseñador", opc.autor or "—"],
        ["Norma de diseño", "NTP E.060 Concreto Armado (RNE)"],
        ["Norma sísmica", opc.norma_sismo],
    ], titulo="Tabla 1. Identificación del elemento", alinear="l")

    doc.h2("Materiales y datos de diseño", "2.")
    ec = normas.modulo_elasticidad_concreto(fc)
    doc.tabla(["Parámetro", "Símbolo", "Valor", "Referencia"], [
        ["Resistencia del concreto", "f'c", f"{ff(fc,0)} kgf/cm²", "E.060 5.1"],
        ["Fluencia del acero", "fy", f"{ff(fy,0)} kgf/cm²", "E.060 6.4 (Grado 60)"],
        ["Módulo de elasticidad del concreto", "Ec", f"{ff(ec,0)} kgf/cm²", "E.060 8.5.1"],
        ["Módulo de elasticidad del acero", "Es", "2 000 000 kgf/cm²", "E.060 8.5.2"],
        ["Factor β1", "β1", ff(normas.beta1(fc), 3), "E.060 10.2.7.3"],
        ["Factor de reducción (flexión)", "φf", "0.90", "E.060 9.3.2.1"],
        ["Factor de reducción (corte)", "φv", "0.85" if not sismico else "0.60 – 0.85",
         "E.060 9.3.2.3 / 21.2.4"],
        ["Recubrimiento libre", "r", f"{ff(rec,1)} cm", "E.060 7.7.1"],
        ["Diámetro de estribo", "db est", f"{ff(dbe,2)} cm (#3)", "—"],
        ["Deformación última del concreto", "εcu", "0.003", "E.060 10.2.3"],
    ], titulo="Tabla 2. Propiedades de los materiales")

    doc.h3("Peralte efectivo")
    doc.formula(f"d = h − r − db_est − db/2\n"
                f"  = {ff(h,1)} − {ff(rec,1)} − {ff(dbe,2)} − 1.905/2",
                f"d ≈ {ff(d0,2)} cm (varilla longitudinal supuesta #6)")

    # ---------------- 3. Solicitaciones ----------------
    doc.h2("Solicitaciones de diseño", "3.")
    filas_sol = []
    for f in r["filas"]:
        filas_sol.append([
            f["estacion"], tm(f["Mu_pos"] * 1e5), tm(f["Mu_neg"] * 1e5),
            tf(f["Vu"] * 1e3),
            tm(f["corte"]["Tu"] if f["corte"] else 0.0),
        ])
    doc.tabla(["Estación", "Mu+ [tonf·m]", "Mu− [tonf·m]", "Vu [tonf]", "Tu [tonf·m]"],
              filas_sol, titulo="Tabla 3. Envolventes por estación")
    doc.nota("Los momentos y cortantes provienen de las combinaciones de carga "
             "indicadas en el modelo de ETABS; los valores ya incluyen los factores "
             "de amplificación de carga (E.060 9.2 / E.030).")

    filas_combos = []
    for f in r["filas"]:
        filas_combos.append([f["estacion"],
                             _html.escape(str(f.get("combo_pos") or "—")),
                             _html.escape(str(f.get("combo_neg") or "—"))])
    combinaciones = sorted(set(el.combos))
    if combinaciones:
        doc.tabla(["Combinación"], [[_html.escape(c)] for c in combinaciones],
                  titulo="Tabla 4. Combinaciones de carga consideradas")

    # ---------------- 4. Flexión ----------------
    doc.h2("Diseño por flexión", "4.")
    doc.h3("4.1 Acero mínimo y máximo")
    doc.formula(
        "As,mín = máx( 0.7·√f'c / fy ; 14 / fy ) · b · d          (E.060 10.5.1)\n"
        f"       = máx( 0.7·√{ff(fc,0)}/{ff(fy,0)} ; 14/{ff(fy,0)} ) · "
        f"{ff(b,0)} · {ff(d0,2)}",
        f"As,mín = {cm2(r['As_min'])} cm²   (ρmín = {r['rho_min']*100:.3f} %)")
    doc.formula(
        "As,máx = ρmáx · b · d,  con εt ≥ 0.004  (sección dúctil, E.060 10.3.4 y 21.4.4)\n"
        f"As,máx = {cm2(r['As_max'])} cm²   (ρmáx = {r['rho_max']*100:.2f} %)")
    if sismico:
        doc.formula(
            "Requisito sismorresistente: As ≥ máx(0.25·√f'c/fy ; 1.4/fy)·b·d  (E.060 21.4.4.1)\n"
            f"As,mín,sismo = {cm2(r['As_min_sismo'])} cm²")

    doc.h3("4.2 Acero requerido y refuerzo adoptado")
    doc.p("Para cada estación se calcula el acero requerido resolviendo el bloque "
          "rectangular equivalente de esfuerzos:")
    doc.formula(
        "Mu/φ = 0.85·f'c·b·a·(d − a/2)   y   As = 0.85·f'c·b·a / fy\n"
        "con a = β1·c  (E.060 10.2.7, 10.3.2)")
    filas_flex = []
    for f in r["filas"]:
        pos, neg = f["ref_pos"], f["ref_neg"]
        filas_flex.append([
            f["estacion"],
            tm(f["Mu_pos"] * 1e5), cm2(f["As_pos"]), pos,
            tm(f["phiMn_pos"] * 1e5), f"{f['dcr_pos']:.2f}",
            tm(f["Mu_neg"] * 1e5), cm2(f["As_neg"]), neg,
            tm(f["phiMn_neg"] * 1e5), f"{f['dcr_neg']:.2f}",
        ])
    doc.tabla(["Estación", "Mu+ [t·m]", "As+ [cm²]", "Refuerzo +",
               "φMn+ [t·m]", "D/C", "Mu− [t·m]", "As− [cm²]", "Refuerzo −",
               "φMn− [t·m]", "D/C"], filas_flex,
              titulo="Tabla 5. Diseño de flexión por estación")

    doc.h3("4.3 Verificación de espaciamiento y capas")
    verificados = []
    for est in res["estaciones"]:
        for clave, etiqueta in (("positivo", "As+"), ("negativo", "As−")):
            op = est.get(clave)
            if not op:
                continue
            s_min = max(2.5, 1.33 * op["db"])
            util = b - 2 * (rec + dbe)
            ancho_ocupado = (op["barras_por_capa"] * op["db"]
                             + max(0, op["barras_por_capa"] - 1) * s_min)
            verificados.append([
                est["estacion"], etiqueta,
                f"{op['n']} {op['varilla']}", f"{op['capas']}",
                f"{op['barras_por_capa']}", ff(op["db"], 2),
                ff(s_min, 2), ff(util, 2), ff(ancho_ocupado, 2),
                "CUMPLE" if ancho_ocupado <= util + 1e-6 else "NO CUMPLE",
                f"{op['eps_t']:.4f}",
                "CUMPLE" if op["eps_t"] >= 0.004 else "NO CUMPLE",
            ])
    if verificados:
        doc.tabla(["Estación", "Cara", "Refuerzo", "Capas", "Barras/capa", "db [cm]",
                   "s mín [cm]", "b útil [cm]", "Ancho ocup. [cm]", "Espaciamiento",
                   "εt", "Ductilidad"], verificados,
                  titulo="Tabla 6. Distribución de barras (E.060 7.6.1, 21.4.4)")
        doc.formula("s_libre,mín = máx(2.5 cm ; 1.33·db ; 1.33·agregado)   (E.060 7.6.1)")

    # ---------------- 5. Corte ----------------
    doc.h2("Diseño por corte y torsión", "5.")
    corte = r["corte_gobernante"]
    if corte:
        doc.h3("5.1 Diseño por capacidad (E.060 21.4.5.1)")
        if corte.get("Mpr_i") or corte.get("Mpr_j"):
            doc.p("El cortante sísmico se obtiene a partir de los momentos probables "
                  "en los extremos del elemento (refuerzo real con fy amplificado en 25 %), "
                  "de modo que la rótula plástica se forme antes que la falla por corte:")
            doc.formula(
                "Mpr = 1.25·fy·As·(d − a/2)    con a = 1.25·fy·As/(0.85·f'c·b)\n"
                f"Mpr,i = {tm(corte['Mpr_i'])} tonf·m ; Mpr,j = {tm(corte['Mpr_j'])} tonf·m\n"
                f"Vsismo = (Mpr,i + Mpr,j)/ln = {tf(corte['Vu_capacidad'])} tonf "
                f"(ln = {ff(corte['ln']/100, 2)} m)\n"
                f"Vg = {tf(corte['Vu_grav'])} tonf  →  Vcap = {tf(corte['Vu_capacidad'] + corte['Vu_grav'])} tonf",
                f"Vu de diseño = {tf(corte['Vu_diseno'])} tonf")
            doc.nota("El cortante de diseño es el mayor entre el proveniente de las "
                     "combinaciones de carga y el de capacidad, y en la zona de "
                     "confinamiento se desprecia la contribución del concreto cuando "
                     "el sismoinducido supera el 50 % del total (E.060 21.4.5.2).")
        doc.h3("5.2 Resistencia del concreto")
        doc.formula(
            "Vc = 0.53·√f'c·bw·d·(1 + Nu/(14·Ag))        (E.060 11.3.1.1)\n"
            f"Vc = 0.53·√{ff(fc,0)}·{ff(b,0)}·{ff(corte.get('d', d0),2)}"
            f" = {tf(corte['Vc'])} tonf",
            f"φVc = {tf(corte['phiVc'])} tonf   (φ = {corte['phi']:.2f})")
        if corte.get("vc_cero"):
            doc.nota("Se tomó Vc = 0 en la zona de rótula plástica porque el cortante "
                     "sismoinducido supera el 50 % del cortante total (E.060 21.4.5.2).")

        doc.h3("5.3 Acero requerido")
        doc.formula(
            "Vs,req = Vu/φ − Vc\n"
            f"Vs,req = {tf(corte['Vu'])}/{corte['phi']:.2f} − {tf(corte['Vc'])} = "
            f"{tf(corte['Vs_req'])} tonf")
        doc.formula("Av/s = Vs,req·s/(fy·d)   ;   Av = 2·Aestribo   (rama doble)")
        doc.formula(
            "Av/s,mín = máx(0.062·√f'c·b/fy ; 0.35·b/fy)   (E.060 11.4.6.3)\n"
            f"Av/s,mín = {corte['Av_s_min']:.4f} cm²/cm")
        doc.tabla(["Concepto", "Resto de la luz", "Zona de confinamiento", "Unidad"], [
            ["Cortante de diseño Vu", tf(corte["Vu"]), tf(corte["Vu_conf"]), "tonf"],
            ["Resistencia del concreto Vc", tf(corte["Vc"]), tf(corte["Vc_conf"]), "tonf"],
            ["φVc", tf(corte["phiVc"]), tf(corte["phi_vc_conf"]), "tonf"],
            ["Vs requerido", tf(corte["Vs_req"]), tf(corte["Vs_req_conf"]), "tonf"],
            ["Av (2 ramas)", ff(corte["Av"], 3), ff(corte["Av"], 3), "cm²"],
            ["Av/s requerido", ff(corte["Av_s"], 4), ff(corte["Av_s_conf"], 4), "cm²/cm"],
            ["s requerido", ff(corte["s_req"], 1), ff(corte["s_req_conf"], 1), "cm"],
            ["s adoptado", ff(corte["s_resto"], 1), ff(corte["s_conf"], 1), "cm"],
            ["φVn provisto", tf(corte["phiVn"]), tf(corte["phiVn_conf"]), "tonf"],
            ["D/C corte", f"{corte['dcr_resto']:.3f}", f"{corte['dcr_conf']:.3f}", "—"],
        ], titulo="Tabla 7. Resumen del diseño por corte")
        doc.tabla(["Concepto", "Valor", "Unidad"], [
            ["Vs máximo (2.1·√f'c·bw·d)", tf(corte["Vs_max"]), "tonf"],
            ["Vu máximo de sección φ(Vc+Vs,máx)", tf(corte["vu_max"]), "tonf"],
            ["s máximo (resto)", ff(corte["s_max"], 1), "cm"],
            ["s máximo (confinamiento)", ff(corte["s_conf_lim"], 1), "cm"],
        ], titulo="Tabla 7b. Límites de la sección")
        doc.p(f"Estribos adoptados: <b>{corte['estribo']}</b> de dos ramas "
              f"(Av = {ff(corte['Av'],2)} cm²) con espaciamientos:")
        criterios = {
            "conf": "s ≤ mín(d/4, 8·db_long, 24·db_est, 30 cm) — E.060 21.4.4.2",
            "resto": "s ≤ mín(d/2, 30 cm) y Av/s ≥ Av/s,mín — E.060 11.4.5",
        }
        filas_z = []
        for z in corte["zonas"]:
            es_conf = "onfin" in z["zona"]
            filas_z.append([z["zona"], ff(z["s"], 1),
                            criterios["conf"] if es_conf else criterios["resto"]])
        doc.tabla(["Zona", "Espaciamiento [cm]", "Criterio"], filas_z,
                  titulo="Tabla 8. Distribución de estribos")
        doc.figura(figuras.svg_estribos(L, corte.get("zona_conf_cm", min(2*h, 60.0)),
                                        corte["s_conf"], corte["s_resto"], b, h),
                   "Figura 3. Distribución de estribos a lo largo de la viga")

        doc.h3("5.4 Torsión")
        tor = res["estaciones"][0].get("torsion") if res["estaciones"] else None
        if tor:
            doc.formula(
                "Tcr = 0.27·√f'c·Acp²/Pcp   y   φTcr = 0.85·Tcr   (E.060 11.5.2.2)\n"
                f"Acp = {ff(tor['Acp'],0)} cm² ; Pcp = {ff(tor['Pcp'],0)} cm\n"
                f"Tcr = {tm(tor['Tcr'])} tonf·m",
                f"φTcr = {tm(tor['phiTcr'])} tonf·m")
            doc.p("La torsión se considera de compatibilidad; el refuerzo transversal "
                  "por torsión se suma al de corte y el longitudinal se distribuye en "
                  "el perímetro del estribo (E.060 11.5.3).")
            doc.tabla(["Concepto", "Valor"], [
                ["Torsor último Tu", f"{tm(corte['Tu'])} tonf·m"],
                ["Torsor de agrietamiento φTcr", f"{tm(tor['phiTcr'])} tonf·m"],
                ["¿Requiere refuerzo por torsión?",
                 "SÍ" if tor["requiere_armadura"] else "NO"],
                ["At/s requerido", f"{ff(tor['Ats'],4)} cm²/cm"],
                ["At/s mínimo", f"{ff(tor['Ats_min'],4)} cm²/cm"],
                ["Al mínimo", f"{ff(tor['Al_min'],2)} cm²"],
                ["Aoh", f"{ff(tor['Aoh'],0)} cm²"],
            ], titulo="Tabla 9. Verificación de torsión")
        else:
            doc.p("No se reportan torsores significativos en las combinaciones analizadas.")

    # ---------------- 6. Requisitos sísmicos ----------------
    if sismico and r["verificaciones"]:
        doc.h2("Requisitos de pórticos sismorresistentes", "6.")
        filas_v = []
        for v in r["verificaciones"]:
            valor = v.get("valor")
            limite = v.get("limite")
            fmt = (lambda x: ff(x, 3)) if isinstance(valor, float) and abs(valor) < 20 else (
                lambda x: ff(x, 1) if isinstance(x, (int, float)) else str(x))
            filas_v.append([v["nombre"], fmt(valor), fmt(limite), _si(v["cumple"]),
                            v.get("ref", "")])
        doc.tabla(["Requisito", "Valor", "Límite", "Resultado", "Referencia"], filas_v,
                  titulo="Tabla 10. Verificación de requisitos normativos")
        doc.p("Las vigas que forman parte del sistema sismorresistente deben cumplir "
              "además con la condición de columna fuerte–viga débil en los nudos "
              "(E.060 21.4.2.2), verificada en el modelo global del ETABS.")

    # ---------------- 7. Verificaciones ----------------
    doc.h2("Resumen de verificaciones", "7.")
    from .servicio import verificar_resultado
    checks = verificar_resultado(salida)
    filas_chk = []
    for c in checks:
        valor = c.get("valor")
        limite = c.get("limite")
        filas_chk.append([
            c["nombre"],
            ff(valor, 3) if isinstance(valor, (int, float)) else (valor if valor is not None else "—"),
            ff(limite, 3) if isinstance(limite, (int, float)) else (limite if limite is not None else "—"),
            _si(c.get("cumple")), c.get("ref", "")])
    doc.tabla(["Verificación", "Valor", "Límite", "Resultado", "Referencia"],
              filas_chk, titulo="Tabla 11. Cuadro de verificaciones")

    # ---------------- 8. Conclusiones ----------------
    doc.h2("Conclusiones y detalle final", "8.")
    ref_pos = [f for f in r["filas"] if f["ref_pos"] != "—"]
    ref_neg = [f for f in r["filas"] if f["ref_neg"] != "—"]
    doc.lista([
        f"Sección: {ff(b,0)} × {ff(h,0)} cm, f'c = {ff(fc,0)} kgf/cm², "
        f"fy = {ff(fy,0)} kgf/cm².",
        f"Refuerzo superior (momentos negativos): "
        f"{ref_neg[0]['ref_neg'] if ref_neg else 'mínimo por norma'}"
        f" — As = {cm2(max((f['As_neg'] for f in r['filas']), default=0.0))} cm².",
        f"Refuerzo inferior (momentos positivos): "
        f"{max(ref_pos, key=lambda f: f['As_pos'])['ref_pos'] if ref_pos else 'mínimo por norma'}"
        f" — As = {cm2(max((f['As_pos'] for f in r['filas']), default=0.0))} cm².",
        f"Estribos: {corte['estribo'] if corte else '#3'} @ "
        f"{ff(corte['s_conf'],1) if corte else '—'} cm en la zona de confinamiento "
        f"(0 a {ff(corte.get('zona_conf_cm', 0),0) if corte else '—'} cm) y @ "
        f"{ff(corte['s_resto'],1) if corte else '—'} cm en el resto de la luz.",
        f"Verificación global: {'SATISFACTORIA (todos los estados cumplen)' if all(c.get('cumple') for c in checks) else 'REVISAR los estados marcados NO CUMPLE'}.",
    ])
    doc.nota("Esta memoria se genera automáticamente a partir de las solicitaciones "
             "importadas del modelo. El detalle de armado final (anclajes, empalmes, "
             "ganchos y compatibilidad con otras especialidades) debe completarse en "
             "los planos de estructuras.")

    # ---------------- Anexos ----------------
    doc.h1("Anexos gráficos")
    from .viga import posiciones_longitudinales
    est_pos = max(res["estaciones"],
                  key=lambda e: (e.get("positivo") or {}).get("area", 0.0))
    est_neg = max(res["estaciones"],
                  key=lambda e: (e.get("negativo") or {}).get("area", 0.0))
    barras = posiciones_longitudinales(est_pos.get("positivo"), b, h, rec, dbe,
                                       "inferior")
    barras += posiciones_longitudinales(est_neg.get("negativo"), b, h, rec, dbe,
                                        "superior")
    if not barras:
        barras = [(-b / 2 + rec + 5, -h / 2 + rec + 5, 1.905)] * 2
    doc.figura(figuras.svg_seccion(b, h, rec, dbe, barras,
                                   f"Sección {ff(b,0)}×{ff(h,0)} cm"),
               "Figura 1. Sección transversal con refuerzo longitudinal")
    doc.figura(figuras.svg_envolvente(salida["envolventes"], L),
               "Figura 2. Envolvente de momentos flectores M3")
    return doc


# ===========================================================================
# Memoria de una columna
# ===========================================================================
def memoria_columna(salida: dict) -> Doc:
    el = salida["elemento"]
    opc = salida["opciones"]
    res = salida["resultado"]
    r = salida["resumen"]
    b, h, fc, fy = res["b"], res["h"], res["fc"], res["fy"]
    rec = opc.recubrimiento
    e = res["entrada"]

    doc = Doc("MEMORIA DE CÁLCULO — COLUMNA DE CONCRETO ARMADO",
              f"Norma Técnica Peruana E.060 Concreto Armado · {el.nombre}")
    doc.nota(f"Documento generado el {salida['fecha']} por el sistema "
             f"<b>Diseño E.060 + ETABS</b>. Revisión y firma por el ingeniero "
             f"estructural responsable.")

    doc.h2("Datos generales", "1.")
    doc.tabla(["Concepto", "Valor"], [
        ["Proyecto", opc.proyecto or "—"],
        ["Ubicación", opc.ubicacion or "—"],
        ["Elemento", f"{el.nombre} ({el.tipo})"],
        ["Nivel / Piso", el.story or "—"],
        ["Sección", f"{ff(b,0)} × {ff(h,0)} cm ({el.seccion or '—'})"],
        ["Longitud libre / altura", f"{ff(e.L/100,2)} m"],
        ["Fuente de solicitaciones", el.origen or "—"],
        ["Diseñador", opc.autor or "—"],
        ["Norma de diseño", "NTP E.060 Concreto Armado (RNE)"],
        ["Norma sísmica", opc.norma_sismo],
    ], titulo="Tabla 1. Identificación del elemento")

    doc.h2("Materiales", "2.")
    ec = normas.modulo_elasticidad_concreto(fc)
    doc.tabla(["Parámetro", "Símbolo", "Valor", "Referencia"], [
        ["Resistencia del concreto", "f'c", f"{ff(fc,0)} kgf/cm²", "E.060 5.1"],
        ["Fluencia del acero", "fy", f"{ff(fy,0)} kgf/cm²", "E.060 6.4"],
        ["Módulo de elasticidad", "Ec", f"{ff(ec,0)} kgf/cm²", "E.060 8.5.1"],
        ["Factor β1", "β1", ff(normas.beta1(fc), 3), "E.060 10.2.7.3"],
        ["Recubrimiento libre", "r", f"{ff(rec,1)} cm", "E.060 7.7.1"],
        ["Estribo", "db est", "0.953 cm (#3)", "—"],
    ], titulo="Tabla 2. Propiedades de los materiales")

    doc.h2("Solicitaciones de diseño", "3.")
    doc.p("Se emplean las combinaciones de carga del modelo. Para la verificación "
          "de flexo-compresión biaxial se consideran los estados críticos de cada "
          "combinación (máximo |M3|, máximo |M2|, máxima y mínima carga axial).")
    filas_sol = []
    for d in e.demandas[:16]:
        filas_sol.append([_html.escape(d.combo), tf(d.P), tm(abs(d.M3)), tm(abs(d.M2))])
    doc.tabla(["Combinación", "P [tonf]", "|M3| [tonf·m]", "|M2| [tonf·m]"],
              filas_sol, titulo="Tabla 3. Estados de carga críticos")
    doc.formula(
        f"Pu,máx = {tf(r['Pu'])} tonf   (compresión)\n"
        f"Pu,mín = {tf(min((d.P for d in e.demandas), default=0.0))} tonf\n"
        f"|M3|máx = {tm(r['Mux'])} tonf·m   ;   |M2|máx = {tm(r['Muy'])} tonf·m")

    doc.h2("Efectos de esbeltez", "4.")
    esb = res["esbeltez"]
    doc.formula(
        "r = 0.30·b   (sección rectangular)\n"
        f"r = 0.30·{ff(min(b,h),0)} = {ff(esb['r'],2)} cm\n"
        "k·lu/r ≤ 34 − 12·(M1/M2) ≤ 40     (E.060 10.10.1.1)\n"
        f"k·lu/r = {ff(esb['k'],2)}·{ff(esb['lu'],1)}/{ff(esb['r'],2)} = "
        f"{ff(esb['klu_r'],1)}\n"
        f"límite = 34 − 12·({esb['M1_M2']:.2f}) = {ff(esb['limite'],1)}")
    esb = res["esbeltez"]
    doc.tabla(["Concepto", "Valor"], [
        ["Radio de giro r", f"{ff(esb['r'],2)} cm"],
        ["Longitud efectiva k·lu", f"{ff(esb['k']*esb['lu'],1)} cm"],
        ["Esbeltez k·lu/r", ff(esb["klu_r"], 1)],
        ["Límite 34 − 12(M1/M2)", ff(esb["limite"], 1)],
        ["¿Efectos de esbeltez significativos?", "SÍ" if esb["esbelto"] else "NO"],
        ["Cm = 0.6 + 0.4(M1/M2) ≥ 0.4", ff(esb.get("Cm", 0.6), 3)],
        ["Pc eje 3 = π²·EI/(k·lu)²", tf(esb.get("Pc3", 0.0)) + " tonf"],
        ["Pc eje 2 = π²·EI/(k·lu)²", tf(esb.get("Pc2", 0.0)) + " tonf"],
        ["δns (flexión sobre h, M3)", ff(res.get("delta_3", 1.0), 3)],
        ["δns (flexión sobre b, M2)", ff(res.get("delta_2", 1.0), 3)],
        ["¿Se amplificaron los momentos?", "SÍ" if max(res.get("delta_3", 1), res.get("delta_2", 1)) > 1.0 else "NO"],
    ], titulo="Tabla 4. Verificación de esbeltez (E.060 10.10)")
    doc.formula(
        "δns = Cm / (1 − Pu/(0.75·Pc)) ≥ 1.0\n"
        "Pc  = π²·EI/(k·lu)²   ;   EI = 0.4·Ec·Ig/(1 + βdns)\n"
        "Ig3 = b·h³/12 (flexión sobre h)   ;   Ig2 = h·b³/12 (flexión sobre b)",
        "E.060 10.10.7")
    doc.p("Adicionalmente se controla la excentricidad mínima "
          "M<sub>mín</sub> = Pu·(1.5 + 0.03·h) (E.060 10.10.6.5), de modo que la "
          "columna se verifica aun cuando el análisis entregue momentos nulos: "
          f"M<sub>mín,3</sub> = {tm(res['Mr_min']['M3'])} tonf·m y "
          f"M<sub>mín,2</sub> = {tm(res['Mr_min']['M2'])} tonf·m.")
    if esb["esbelto"] and not res["delta"] > 1.0:
        doc.nota("La columna es esbelta: los momentos deben tomarse del análisis de "
                 "segundo orden de ETABS o activar la magnificación en el programa "
                 "(E.060 10.10.7).")

    doc.h2("Refuerzo longitudinal y verificación flexo-compresión", "5.")
    doc.p("El refuerzo se verifica mediante compatibilidad de deformaciones sobre la "
          "sección completa, considerando el bloque rectangular equivalente de "
          "esfuerzos y el acero elastoplástico. Para flexión biaxial se construye la "
          "superficie de interacción P-Mx-My y se resuelve la capacidad en la "
          "dirección exacta del momento demandado.")
    doc.formula(
        "P0 = 0.85·f'c·(Ag − As) + fy·As            (E.060 10.3.6)\n"
        f"Ag = {ff(b*h,0)} cm² ; As = {cm2(res['barras']['As'])} cm²\n"
        f"P0 = {tf(res['P0'])} tonf\n"
        "φPn,máx = 0.80·φ·P0   (estribos) / 0.85·φ·P0 (zunchos)\n"
        f"φPn,máx = {tf(res['phiPn_max'])} tonf")
    doc.tabla(["Concepto", "Valor"], [
        ["Refuerzo adoptado", res["barras"]["descripcion"]],
        ["Área de acero As", f"{cm2(res['barras']['As'])} cm²"],
        ["Cuantía ρ = As/Ag", f"{res['barras']['rho']*100:.2f} %"],
        ["Límite de cuantía", "1 % ≤ ρ ≤ 6 % (E.060 10.9.1)"],
        ["Carga axial P0", f"{tf(res['P0'])} tonf"],
        ["φPn,máx", f"{tf(res['phiPn_max'])} tonf"],
        ["D/C flexo-compresión biaxial máximo", f"{res['dcr']:.3f}"],
    ], titulo="Tabla 5. Refuerzo y capacidad")

    filas_dcr = []
    for det in res["detalle_demanda"][:22]:
        d = det["demanda"]
        info = det["info"]
        filas_dcr.append([
            _html.escape(d.combo), tf(d.P), tm(det.get("Mux", abs(d.M3))),
            tm(det.get("Muy", abs(d.M2))), tm(info.get("Mcap", 0.0)),
            f"{info.get('phi', 0.0):.2f}", f"{info.get('eps_t', 0.0):.4f}",
            f"{det['dcr']:.3f}", _si(det["dcr"] <= 1.0)])
    doc.tabla(["Combinación", "Pu [tonf]", "Mux = M3 [t·m]", "Muy = M2 [t·m]",
               "φMcap [t·m]", "φ", "εt", "D/C", "Resultado"], filas_dcr,
              titulo="Tabla 6. Verificación por combinación (flexo-compresión biaxial)")
    doc.formula(
        "D/C = Mdem / φMcap(Pu, α) ≤ 1.0 ,  α = atan2(M2, M3)\n"
        "donde φMcap se obtiene resolviendo P(θ,c) = Pu sobre la superficie de "
        "interacción (θ = orientación del eje neutro, c = profundidad).")

    doc.h2("Refuerzo transversal y confinamiento", "6.")
    est = res["estribos"]
    doc.formula(
        "Ash/s ≥ máx[ 0.3·(Ag/Ach − 1)·f'c/fy ; 0.09·f'c/fy ] · bc   (E.060 21.4.4.4)\n"
        f"Ag = {ff(est['Ag'],0)} cm² ; Ach = {ff(est['Ach'],0)} cm² ; "
        f"bc = {ff(est['bc'],1)} cm\n"
        f"Ash/s = {ff(est['Ash_s'],4)} cm²/cm")
    doc.tabla(["Concepto", "Valor"], [
        ["Diámetro de estribo", f"{est['estribo']} ({ff(est['db_estribo'],2)} cm)"],
        ["Número de ramas", f"{est['ramas']}"],
        ["Ash/s requerido", f"{ff(est['Ash_s'],4)} cm²/cm"],
        ["Ash provisto en s = 10 cm", f"{ff(est['Ash_prov'],3)} cm²"],
        ["Ash requerido en s = 10 cm", f"{ff(est['Ash_req'],3)} cm²"],
        ["¿Cumple confinamiento?", "CUMPLE" if est["cumple_ash"] else "NO CUMPLE"],
        ["Espaciamiento en zona de confinamiento", f"{ff(est['s_conf'],1)} cm"],
        ["Espaciamiento fuera de la zona", f"{ff(est['s_ext'],1)} cm"],
        ["Longitud de confinamiento (lo)", f"{ff(est['longitud_confinamiento'],1)} cm"],
        ["Criterio de espaciamiento",
         "s ≤ mín(b/4, 10 cm, 6·db_long, 24·db_est)"],
    ], titulo="Tabla 7. Confinamiento (E.060 21.4.4.4)")

    doc.h2("Verificación por cortante", "7.")
    cor = res["cortante"]
    doc.tabla(["Concepto", "Valor"], [
        ["Cortante último Vu", f"{tf(cor['Vu'])} tonf"],
        ["Vc del concreto", f"{tf(cor['Vc'])} tonf"],
        ["φVc", f"{tf(cor['phiVc'])} tonf"],
        ["Vs requerido", f"{tf(cor['Vs_req'])} tonf"],
        ["Av (ramas × área)", f"{ff(cor['Av'],3)} cm²"],
        ["Espaciamiento adoptado", f"{ff(cor['s_adoptado'],1)} cm"],
        ["φVn", f"{tf(cor['phiVn'])} tonf"],
        ["D/C corte", f"{cor['dcr']:.2f}"],
    ], titulo="Tabla 8. Cortante en la columna")

    doc.h2("Resumen de verificaciones", "8.")
    filas_v = []
    for v in res["verificaciones"]:
        valor = v.get("valor")
        limite = v.get("limite")
        filas_v.append([
            v["nombre"],
            ff(valor, 3) if isinstance(valor, (int, float)) else str(valor),
            ff(limite, 3) if isinstance(limite, (int, float)) else str(limite),
            _si(v["cumple"]), v.get("ref", "")])
    doc.tabla(["Verificación", "Valor", "Límite", "Resultado", "Referencia"],
              filas_v, titulo="Tabla 9. Cuadro de verificaciones")

    doc.h2("Conclusiones", "9.")
    doc.lista([
        f"Sección {ff(b,0)} × {ff(h,0)} cm con {res['barras']['descripcion']} "
        f"(ρ = {res['barras']['rho']*100:.2f} %).",
        f"Estribos {est['estribo']} de {est['ramas']} ramas @ {ff(est['s_conf'],0)} cm "
        f"en zona de confinamiento (lo = {ff(est['longitud_confinamiento'],0)} cm) y "
        f"@ {ff(est['s_ext'],0)} cm en el resto.",
        f"D/C máximo de flexo-compresión biaxial = {res['dcr']:.3f}.",
        f"Verificación global: "
        f"{'SATISFACTORIA' if all(v['cumple'] for v in res['verificaciones']) else 'REVISAR'}.",
    ])

    # ---------------- Anexos ----------------
    doc.h1("Anexos gráficos")
    barras = res["barras"]["posiciones"]
    doc.figura(figuras.svg_seccion(b, h, rec, est["db_estribo"], barras,
                                   f"Sección {ff(b,0)}×{ff(h,0)} cm — "
                                   f"{res['barras']['descripcion']}"),
               "Figura 1. Sección transversal y distribución del refuerzo")
    # diagrama de interacción con solicitudes
    diag = res["diagramas"][0] if res["diagramas"] else None
    if diag:
        demandas = [(d.P / 1e3, abs(d.M3) / 1e5, d.combo) for d in e.demandas]
        doc.figura(figuras.svg_interaccion(list(zip(diag["P"], diag["M"])), demandas,
                                           "Diagrama de interacción φP–φM (flexión sobre h)"),
                   "Figura 2. Diagrama de interacción y solicitudes de diseño")
    diag2 = res["diagramas"][1] if len(res["diagramas"]) > 1 else None
    if diag2:
        demandas2 = [(d.P / 1e3, abs(d.M2) / 1e5, d.combo) for d in e.demandas]
        doc.figura(figuras.svg_interaccion(list(zip(diag2["P"], diag2["M"])), demandas2,
                                           "Diagrama de interacción φP–φM (flexión sobre b)"),
                   "Figura 3. Diagrama de interacción para el eje menor")
    doc.figura(figuras.svg_envolvente(salida["envolventes"], e.L),
               "Figura 4. Envolvente de momentos M3 en la columna")
    return doc


# ===========================================================================
# API pública
# ===========================================================================
def construir_memoria(salida: dict) -> Doc:
    if salida["tipo"] == "Viga":
        return memoria_viga(salida)
    return memoria_columna(salida)


def guardar_html(salida: dict, ruta: str) -> str:
    doc = construir_memoria(salida)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(doc.html())
    return ruta


def guardar_markdown(salida: dict, ruta: str) -> str:
    doc = construir_memoria(salida)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(doc.markdown())
    return ruta


def guardar_pdf(salida: dict, ruta: str) -> bool:
    doc = construir_memoria(salida)
    return doc.pdf(ruta)


def texto_resumen(salida: dict) -> str:
    """Resumen en texto plano para la interfaz."""
    r = salida["resumen"]
    el = salida["elemento"]
    if salida["tipo"] == "Viga":
        lineas = [f"VIGA {el.nombre} — sección {el.b:.0f}×{el.h:.0f} cm"]
        for f in r["filas"]:
            lineas.append(f"  {f['estacion']:<16} Mu+={f['Mu_pos']:7.2f}  Mu-={f['Mu_neg']:7.2f}  "
                          f"Ref+: {f['ref_pos']:<8} Ref-: {f['ref_neg']:<8}")
        if r["corte_gobernante"]:
            c = r["corte_gobernante"]
            lineas.append(f"  Estribos: {c['estribo']} @ {c['s_conf']:.0f} cm (confinamiento) "
                          f"/ {min(c['s_adoptado'], c['s_max']):.0f} cm (resto)")
        return "\n".join(lineas)
    lineas = [f"COLUMNA {el.nombre} — sección {el.b:.0f}×{el.h:.0f} cm"]
    lineas.append(f"  Refuerzo: {r['refuerzo']}  (ρ = {r['rho']*100:.2f} %)")
    lineas.append(f"  D/C biaxial: {r['dcr']:.3f}")
    lineas.append(f"  Estribos: {r['estribos']}")
    return "\n".join(lineas)
