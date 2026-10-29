"""
Figuras vectoriales (SVG) generadas sin dependencias externas.

Todas las funciones devuelven una cadena SVG autocontenida, de modo que el
informe HTML no necesita archivos adicionales y el PDF puede exportarse con
cualquier visor.

Convención de colores: acero en azul, concreto en gris claro, cotas en gris
oscuro y zonas en falla en rojo.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple

AZUL = "#1f4e79"
AZUL_CLARO = "#9dc3e6"
GRIS = "#7f7f7f"
GRIS_CLARO = "#e7e6e6"
ROJO = "#c00000"
VERDE = "#2e7d32"


def _f(v: float, dec: int = 1) -> str:
    return f"{v:,.{dec}f}".replace(",", " ")


def _svg(ancho: float, alto: float, contenido: str, clase: str = "") -> str:
    estilo = ("text{font-family:Helvetica,Arial,sans-serif;fill:#333}"
              ".t{font-size:11px}.tb{font-size:12px;font-weight:bold}"
              ".eje{stroke:#999;stroke-width:.6}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho:.0f} {alto:.0f}" '
            f'width="100%" class="{clase}" style="max-width:{ancho:.0f}px">'
            f'<style>{estilo}</style>{contenido}</svg>')


# ===========================================================================
# 1. Sección transversal con refuerzo
# ===========================================================================
def svg_seccion(b: float, h: float, recubrimiento: float, db_estribo: float,
                barras: Iterable[Tuple[float, float, float]],
                titulo: str = "", ancho_px: float = 340.0) -> str:
    """
    Dibuja la sección (b × h en cm) con estribo y barras longitudinales.

    barras: iterable de (x, y, db) en cm, con origen en el centroide.
    """
    margen = 42.0
    esc = min((ancho_px - 2 * margen) / max(b, 1e-6), 260.0 / max(h, 1e-6))
    esc = max(1.2, min(esc, 7.0))
    W = b * esc
    H = h * esc
    ox = margen + W / 2.0
    oy = margen + H / 2.0

    def px(x: float) -> float:
        return ox + x * esc

    def py(y: float) -> float:
        return oy - y * esc          # y hacia arriba

    total_alto = H + 2 * margen + 24
    partes = []
    # concreto
    partes.append(f'<rect x="{px(-b/2):.1f}" y="{py(h/2):.1f}" width="{W:.1f}" '
                  f'height="{H:.1f}" fill="{GRIS_CLARO}" stroke="#555" stroke-width="1"/>')
    # estribo
    be = max(b - 2 * recubrimiento - db_estribo, 2.0)
    he = max(h - 2 * recubrimiento - db_estribo, 2.0)
    partes.append(f'<rect x="{px(-be/2):.1f}" y="{py(he/2):.1f}" width="{be*esc:.1f}" '
                  f'height="{he*esc:.1f}" fill="none" stroke="{AZUL}" '
                  f'stroke-width="{max(1.0, db_estribo*esc*0.55):.1f}" rx="3"/>')
    # barras
    for (x, y, db) in barras:
        r = max(2.0, db * esc / 2.0 * 1.25)
        partes.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="{r:.1f}" '
                      f'fill="{AZUL}" stroke="#123" stroke-width=".5"/>')
    # cotas
    y_cota = py(-h / 2) + 18
    partes.append(f'<line x1="{px(-b/2):.1f}" y1="{y_cota:.1f}" x2="{px(b/2):.1f}" '
                  f'y2="{y_cota:.1f}" class="eje"/>')
    partes.append(f'<text x="{px(0):.1f}" y="{y_cota+13:.1f}" class="t" '
                  f'text-anchor="middle">b = {_f(b,0)} cm</text>')
    x_cota = px(-b / 2) - 20
    partes.append(f'<line x1="{x_cota:.1f}" y1="{py(-h/2):.1f}" x2="{x_cota:.1f}" '
                  f'y2="{py(h/2):.1f}" class="eje"/>')
    partes.append(f'<text x="{x_cota-4:.1f}" y="{py(0):.1f}" class="t" '
                  f'text-anchor="middle" transform="rotate(-90 {x_cota-4:.1f} {py(0):.1f})">'
                  f'h = {_f(h,0)} cm</text>')
    if titulo:
        partes.append(f'<text x="{ox:.1f}" y="{py(h/2)-10:.1f}" class="tb" '
                      f'text-anchor="middle">{titulo}</text>')
    return _svg(ancho_px, total_alto, "".join(partes))


# ===========================================================================
# 2. Diagrama de interacción P-M
# ===========================================================================
def svg_interaccion(puntos: Sequence[Tuple[float, float]],
                    demandas: Sequence[Tuple[float, float, str]] = (),
                    titulo: str = "Diagrama de interacción φPn – φMn",
                    sigma: float = 1.0) -> str:
    """
    puntos  : [(P, M)] del diagrama de diseño en tonf y tonf·m.
    demandas: [(Pu, Mu, etiqueta)] solicitaciones de diseño, mismas unidades.
    """
    if not puntos:
        return _svg(320, 240, "<text x='10' y='20' class='t'>Sin datos</text>")
    ancho, alto = 460.0, 340.0
    ml, mr, mt, mb = 58.0, 18.0, 32.0, 40.0
    Ps = [p for p, _ in puntos] + [d[0] for d in demandas]
    Ms = [m for _, m in puntos] + [d[1] for d in demandas]
    p_max = max(max(Ps), 1.0) * 1.08
    p_min = min(min(Ps), 0.0) - abs(min(Ps)) * 0.10 - 1.0
    m_max = max(max(Ms), 1.0) * 1.12
    if p_max <= p_min:
        p_max = p_min + 10.0

    def px(m: float) -> float:
        return ml + (m / m_max) * (ancho - ml - mr)

    def py(p: float) -> float:
        return alto - mb - (p - p_min) / (p_max - p_min) * (alto - mt - mb)

    partes = [f'<rect x="{ml}" y="{mt}" width="{ancho-ml-mr:.1f}" '
              f'height="{alto-mt-mb:.1f}" fill="#fbfbfb" stroke="#ccc"/>']
    # retícula
    for i in range(1, 5):
        f = i / 4
        y = py(p_min + f * (p_max - p_min))
        x = px(f * m_max)
        partes.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ancho-mr:.1f}" y2="{y:.1f}" '
                      f'stroke="#eee"/>')
        partes.append(f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{alto-mb:.1f}" stroke="#eee"/>')
        partes.append(f'<text x="{ml-6:.1f}" y="{y+4:.1f}" class="t" text-anchor="end">'
                      f'{_f(p_min + f*(p_max-p_min),0)}</text>')
        partes.append(f'<text x="{x:.1f}" y="{alto-mb+14:.1f}" class="t" text-anchor="middle">'
                      f'{_f(f*m_max,1)}</text>')
    # eje P = 0
    if p_min < 0 < p_max:
        partes.append(f'<line x1="{ml}" y1="{py(0):.1f}" x2="{ancho-mr:.1f}" y2="{py(0):.1f}" '
                      f'stroke="#999" stroke-dasharray="4 3"/>')
    # curva
    d = " ".join(f'{"M" if i == 0 else "L"}{px(m):.1f},{py(p):.1f}'
                 for i, (p, m) in enumerate(puntos))
    partes.append(f'<path d="{d}" fill="none" stroke="{AZUL}" stroke-width="2.2"/>')
    # demandas
    for (p, m, et) in demandas:
        partes.append(f'<circle cx="{px(m):.1f}" cy="{py(p):.1f}" r="3.4" fill="{ROJO}"/>')
    # rótulos de ejes
    partes.append(f'<text x="{(ml+ancho-mr)/2:.1f}" y="{alto-8:.1f}" class="t" '
                  f'text-anchor="middle">Momento φMn [tonf·m]</text>')
    partes.append(f'<text x="14" y="{(mt+alto-mb)/2:.1f}" class="t" text-anchor="middle" '
                  f'transform="rotate(-90 14 {(mt+alto-mb)/2:.1f})">Carga axial φPn [tonf]</text>')
    partes.append(f'<text x="{(ml+ancho-mr)/2:.1f}" y="18" class="tb" '
                  f'text-anchor="middle">{titulo}</text>')
    if demandas:
        partes.append(f'<circle cx="{ancho-mr-96:.1f}" cy="{mt+14:.1f}" r="3.4" fill="{ROJO}"/>')
        partes.append(f'<text x="{ancho-mr-88:.1f}" y="{mt+18:.1f}" class="t">demanda</text>')
    return _svg(ancho, alto, "".join(partes))


# ===========================================================================
# 3. Envolvente de momentos de una viga
# ===========================================================================
def svg_envolvente(envolventes: Sequence[dict], L: float,
                   titulo: str = "Envolvente de momentos flectores M3 [tonf·m]") -> str:
    """
    Envolvente de momentos a lo largo del elemento.

    Acepta la salida de ``Elemento.envolventes()`` (claves ``estacion``,
    ``Mu_pos``, ``Mu_neg``) o la forma reducida (``x``, ``M_pos``, ``M_neg``).
    Unidades de entrada: kgf·cm.
    """
    xs, pos, neg = [], [], []
    for env in envolventes:
        x = env.get("x", env.get("estacion", 0.0))
        if "M" in env:
            m = env["M"]
            (pos if m >= 0 else neg).append((x, m))
        else:
            xs.append(x)
            pos.append((x, env.get("Mu_pos", env.get("M_pos", 0.0))))
            neg.append((x, -abs(env.get("Mu_neg", env.get("M_neg", 0.0)))))
    if not pos and not neg:
        return _svg(320, 200, "<text x='10' y='20' class='t'>Sin datos</text>")
    ancho, alto = 480.0, 250.0
    ml, mr, mt, mb = 56.0, 16.0, 34.0, 36.0
    todos = [m for _, m in pos + neg]
    m_max = max(max(abs(m) for m in todos), 1.0) * 1.15
    L = max(L, max((x for x, _ in pos + neg), default=1.0), 1e-6)

    def px(x: float) -> float:
        return ml + min(max(x, 0.0), L) / L * (ancho - ml - mr)

    def py(m: float) -> float:
        return mt + (alto - mt - mb) / 2.0 - m / m_max * (alto - mt - mb) / 2.0

    partes = [f'<rect x="{ml}" y="{mt}" width="{ancho-ml-mr:.1f}" '
              f'height="{alto-mt-mb:.1f}" fill="#fbfbfb" stroke="#ccc"/>']
    for serie, color in ((pos, AZUL), (neg, ROJO)):
        serie = sorted(serie, key=lambda t: t[0])
        if len(serie) < 2:
            continue
        d = " ".join(f'{"M" if i == 0 else "L"}{px(x):.1f},{py(m):.1f}'
                     for i, (x, m) in enumerate(serie))
        partes.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
        partes.append(f'<path d="{d} L{px(serie[-1][0]):.1f},{py(0):.1f} '
                      f'L{px(serie[0][0]):.1f},{py(0):.1f} Z" fill="{color}" opacity="0.10"/>')
    partes.append(f'<line x1="{ml}" y1="{py(0):.1f}" x2="{ancho-mr:.1f}" y2="{py(0):.1f}" '
                  f'stroke="#888"/>')
    for valor in (m_max, 0.0, -m_max):
        partes.append(f'<text x="{ml-6:.1f}" y="{py(valor)+4:.1f}" class="t" '
                      f'text-anchor="end">{_f(valor/1e5,1)}</text>')
    for i in range(1, 4):
        x = px(L * i / 4.0)
        partes.append(f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{alto-mb:.1f}" stroke="#eee"/>')
        partes.append(f'<text x="{x:.1f}" y="{alto-mb+14:.1f}" class="t" '
                      f'text-anchor="middle">{_f(L*i/4.0/100,1)}</text>')
    partes.append(f'<text x="14" y="{(mt+alto-mb)/2:.1f}" class="t" text-anchor="middle" '
                  f'transform="rotate(-90 14 {(mt+alto-mb)/2:.1f})">M [tonf·m]</text>')
    partes.append(f'<text x="{(ml+ancho-mr)/2:.1f}" y="{alto-6:.1f}" class="t" '
                  f'text-anchor="middle">Estación [m]</text>')
    partes.append(f'<text x="{(ml+ancho-mr)/2:.1f}" y="18" class="tb" '
                  f'text-anchor="middle">{titulo}</text>')
    return _svg(ancho, alto, "".join(partes))


# ===========================================================================
# 4. Alzado de estribos de una viga
# ===========================================================================
def svg_estribos(L: float, zona_conf: float, s_conf: float, s_resto: float,
                 b: float, h: float, titulo: str = "Distribución de estribos") -> str:
    """Alzado esquemático de la viga con las zonas de confinamiento."""
    ancho, alto = 480.0, 150.0
    ml, mr = 30.0, 30.0
    y0, y1 = 46.0, 86.0
    L = max(L, 1e-6)

    def px(x: float) -> float:
        return ml + x / L * (ancho - ml - mr)

    partes = [f'<rect x="{px(0):.1f}" y="{y0}" width="{px(L)-px(0):.1f}" '
              f'height="{y1-y0}" fill="{GRIS_CLARO}" stroke="#666"/>']
    # zonas confinadas
    for x0, x1 in ((0.0, zona_conf), (L - zona_conf, L)):
        x0 = max(0.0, x0)
        x1 = min(L, x1)
        if x1 <= x0:
            continue
        partes.append(f'<rect x="{px(x0):.1f}" y="{y0}" width="{px(x1)-px(x0):.1f}" '
                      f'height="{y1-y0}" fill="{AZUL}" opacity=".18"/>')
    # estribos
    def paso(x0: float, x1: float, s: float) -> None:
        if s <= 0:
            return
        x = x0 + s / 2.0
        while x < x1:
            partes.append(f'<line x1="{px(x):.1f}" y1="{y0}" x2="{px(x):.1f}" y2="{y1}" '
                          f'stroke="{AZUL}" stroke-width="1"/>')
            x += s

    paso(0.0, zona_conf, s_conf)
    paso(zona_conf, L - zona_conf, s_resto)
    paso(L - zona_conf, L, s_conf)
    partes.append(f'<text x="{px(zona_conf/2):.1f}" y="{y1+16:.1f}" class="t" '
                  f'text-anchor="middle">@{_f(s_conf,1)} cm</text>')
    partes.append(f'<text x="{px(L/2):.1f}" y="{y1+16:.1f}" class="t" text-anchor="middle">'
                  f'@{_f(s_resto,1)} cm</text>')
    partes.append(f'<text x="{px(L-zona_conf/2):.1f}" y="{y1+16:.1f}" class="t" '
                  f'text-anchor="middle">@{_f(s_conf,1)} cm</text>')
    partes.append(f'<text x="{px(zona_conf/2):.1f}" y="{y0-6:.1f}" class="t" '
                  f'text-anchor="middle">2h ≤ 60 cm</text>')
    partes.append(f'<text x="{(ml+ancho-mr)/2:.1f}" y="18" class="tb" '
                  f'text-anchor="middle">{titulo}</text>')
    partes.append(f'<text x="{(ml+ancho-mr)/2:.1f}" y="{alto-4:.1f}" class="t" '
                  f'text-anchor="middle">L = {_f(L,0)} cm · sección {_f(b,0)}×{_f(h,0)} cm</text>')
    return _svg(ancho, alto, "".join(partes))
