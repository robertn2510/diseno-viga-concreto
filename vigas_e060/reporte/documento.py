"""Modelo de documento independiente del formato de salida."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TipoBloque = Literal[
    "h1", "h2", "h3", "h4", "p", "bullets", "tabla", "formula", "nota", "salto"
]


@dataclass
class Bloque:
    tipo: TipoBloque
    texto: str = ""
    nivel: int = 0
    items: list[str] = field(default_factory=list)
    encabezados: list[str] = field(default_factory=list)
    filas: list[list[str]] = field(default_factory=list)
    anchos: list[float] | None = None
    referencia: str = ""


class Documento:
    """Contenedor secuencial de bloques de memoria."""

    def __init__(self) -> None:
        self.bloques: list[Bloque] = []

    def h1(self, texto: str) -> None:
        self.bloques.append(Bloque("h1", texto=texto, nivel=1))

    def h2(self, texto: str) -> None:
        self.bloques.append(Bloque("h2", texto=texto, nivel=2))

    def h3(self, texto: str) -> None:
        self.bloques.append(Bloque("h3", texto=texto, nivel=3))

    def h4(self, texto: str) -> None:
        self.bloques.append(Bloque("h4", texto=texto, nivel=4))

    def p(self, texto: str) -> None:
        self.bloques.append(Bloque("p", texto=texto))

    def bullets(self, items: list[str]) -> None:
        self.bloques.append(Bloque("bullets", items=list(items)))

    def tabla(
        self,
        encabezados: list[str],
        filas: list[list[str]],
        anchos: list[float] | None = None,
    ) -> None:
        self.bloques.append(Bloque(
            "tabla",
            encabezados=list(encabezados),
            filas=[list(f) for f in filas],
            anchos=anchos,
        ))

    def formula(self, texto: str, referencia: str = "") -> None:
        self.bloques.append(Bloque("formula", texto=texto.strip("\n"), referencia=referencia))

    def nota(self, texto: str) -> None:
        self.bloques.append(Bloque("nota", texto=texto))

    def salto(self) -> None:
        self.bloques.append(Bloque("salto"))

    def extender(self, otros: list[Bloque]) -> None:
        self.bloques.extend(otros)
