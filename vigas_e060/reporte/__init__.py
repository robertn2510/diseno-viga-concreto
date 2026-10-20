"""Generación de la memoria de cálculo en Markdown y DOCX."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..config import ConfiguracionDiseno
from ..modelos import MetadatosProyecto, ResultadoViga, VerificacionCombo
from .documento import Documento
from .generador import construir_memoria
from .markdown import renderizar_markdown

__all__ = [
    "Documento",
    "construir_memoria",
    "generar_reporte",
    "renderizar_markdown",
]


def _slug(texto: str) -> str:
    limpio = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚáéíóúÑñ_-]+", "_", texto.strip())
    return limpio.strip("_")[:60] or "proyecto"


def generar_reporte(
    resultados: list[ResultadoViga],
    metadatos: MetadatosProyecto,
    verificaciones_combos: list[VerificacionCombo],
    combos_diseno_etabs: list[str] | None = None,
    config: ConfiguracionDiseno | None = None,
    ruta_salida: str | Path | None = None,
    formatos: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Path | list[str]]:
    """
    Genera la memoria de cálculo.

    Devuelve un diccionario con las rutas creadas y la lista de errores no
    fatales (por ejemplo, si python-docx no está instalado).
    """
    config = config or ConfiguracionDiseno()
    formatos = tuple(
        f.lower() for f in (config.formatos if formatos is None else formatos)
    )
    base_dir = Path(ruta_salida or config.directorio_salida)
    base_dir.mkdir(parents=True, exist_ok=True)

    marca = datetime.now().strftime("%Y%m%d_%H%M")
    base = base_dir / f"memoria_vigas_E060_{_slug(metadatos.proyecto)}_{marca}"

    doc = construir_memoria(
        resultados,
        metadatos,
        verificaciones_combos,
        combos_diseno_etabs or [],
        config,
    )

    salidas: dict[str, Path | list[str]] = {"documento": doc, "errores": []}
    errores: list[str] = salidas["errores"]  # type: ignore[assignment]

    if "md" in formatos:
        ruta_md = base.with_suffix(".md")
        ruta_md.write_text(renderizar_markdown(doc), encoding="utf-8")
        salidas["md"] = ruta_md

    if "docx" in formatos:
        ruta_docx = base.with_suffix(".docx")
        try:
            from .docx_render import renderizar_docx

            renderizar_docx(
                doc,
                ruta_docx,
                encabezado=f"{metadatos.proyecto} — Memoria E.060",
            )
            salidas["docx"] = ruta_docx
        except Exception as exc:
            errores.append(
                f"No se pudo generar DOCX: {exc} Use --formato md o instale python-docx."
            )

    if not any(k in salidas for k in ("md", "docx")):
        raise RuntimeError(
            "No se generó ningún archivo de memoria. " + " ".join(errores)
        )
    return salidas
