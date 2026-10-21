"""Renderizador Markdown de la memoria de cálculo."""

from __future__ import annotations

from .documento import Documento


def _celda(texto: str) -> str:
    return str(texto).replace("|", "\\|").replace("\n", "<br>")


def renderizar_markdown(doc: Documento) -> str:
    lineas: list[str] = []
    for b in doc.bloques:
        if b.tipo == "h1":
            lineas += ["", f"# {b.texto}", ""]
        elif b.tipo == "h2":
            lineas += ["", f"## {b.texto}", ""]
        elif b.tipo == "h3":
            lineas += ["", f"### {b.texto}", ""]
        elif b.tipo == "h4":
            lineas += ["", f"#### {b.texto}", ""]
        elif b.tipo == "p":
            lineas += [b.texto, ""]
        elif b.tipo == "bullets":
            lineas += [f"- {i}" for i in b.items] + [""]
        elif b.tipo == "tabla":
            if not b.encabezados:
                continue
            lineas.append("| " + " | ".join(_celda(h) for h in b.encabezados) + " |")
            lineas.append("| " + " | ".join("---" for _ in b.encabezados) + " |")
            for fila in b.filas:
                fila = list(fila) + [""] * (len(b.encabezados) - len(fila))
                lineas.append("| " + " | ".join(_celda(c) for c in fila) + " |")
            lineas.append("")
        elif b.tipo == "formula":
            if b.referencia:
                lineas.append(f"**{b.referencia}**")
            lineas += ["```text", b.texto, "```", ""]
        elif b.tipo == "nota":
            lineas += [f"> **Nota:** {b.texto}", ""]
        elif b.tipo == "salto":
            lineas += ["", "---", ""]
    return "\n".join(lineas).strip() + "\n"
