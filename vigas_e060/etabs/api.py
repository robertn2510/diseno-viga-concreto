"""
Utilidades para consumir la API COM de ETABS desde ``comtypes`` o ``pywin32``.

Los métodos de la API devuelven una tupla con todos los argumentos de salida y,
al final, el código de retorno entero (0 = éxito).  Estas funciones aíslan ese
detalle para que el resto del programa no dependa del wrapper COM.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Iterable


class ETABSError(RuntimeError):
    """Error controlado de conexión, lectura o escritura en ETABS."""


class ETABSSinResultados(ETABSError):
    """No hay resultados de análisis para la combinación solicitada."""


def sin_ret(resultado: Any) -> tuple[Any, ...]:
    """Elimina el código de retorno final de una tupla COM."""
    if isinstance(resultado, tuple) and resultado and type(resultado[-1]) is int:
        return resultado[:-1]
    if isinstance(resultado, tuple):
        return resultado
    return (resultado,)


def ret_de(resultado: Any) -> int:
    """Extrae el código de retorno COM (0 = éxito)."""
    if isinstance(resultado, tuple) and resultado and type(resultado[-1]) is int:
        return int(resultado[-1])
    if type(resultado) is int:
        return int(resultado)
    return 0


def escalar(resultado: Any, indice: int = 0) -> Any:
    """Devuelve un argumento de salida escalar."""
    datos = sin_ret(resultado)
    if not datos:
        raise ETABSError("La API no devolvió datos.")
    return datos[indice]


def lista(resultado: Any, indice: int = 1) -> list[Any]:
    """Devuelve un arreglo de salida como lista de Python."""
    datos = sin_ret(resultado)
    if len(datos) <= indice:
        return []
    valor = datos[indice]
    if valor is None:
        return []
    if isinstance(valor, (list, tuple)):
        return list(valor)
    try:
        return list(valor)
    except TypeError:
        return [valor]


def verificar_ret(resultado: Any, contexto: str) -> None:
    """Lanza ``ETABSError`` si el código de retorno no es cero."""
    codigo = ret_de(resultado)
    if codigo != 0:
        raise ETABSError(f"{contexto} devolvió el código de error {codigo}.")


def normalizar(texto: str) -> str:
    """Mayúsculas, sin acentos y sin espacios para comparar nombres."""
    if texto is None:
        return ""
    n = unicodedata.normalize("NFKD", str(texto))
    n = "".join(c for c in n if not unicodedata.combining(c))
    return "".join(n.upper().split())


def coincide_caso(nombre: str, patron: str) -> bool:
    """Compara nombres de casos/combos de forma tolerante."""
    a, b = normalizar(nombre), normalizar(patron)
    return bool(a) and (a == b or b in a)


def primer_coincidente(nombres: Iterable[str], patrones: Iterable[str]) -> str | None:
    for patron in patrones:
        for nombre in nombres:
            if coincide_caso(nombre, patron):
                return nombre
    return None
