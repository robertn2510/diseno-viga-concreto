"""Configuración central del programa."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConfiguracionDiseno:
    # Materiales por defecto (kgf/cm²)
    fc_default: float = 210.0
    fy_default: float = 4_200.0
    fyt_default: float = 4_200.0

    # Geometría y detalle
    recubrimiento_libre_cm: float = 4.0
    estribo: str = '3/8"'
    fraccion_rho_b: float = 0.75
    max_capas: int = 2
    diametro_long_min_cm: float = 1.27
    diametro_long_max_cm: float = 2.54
    n_max_barras: int = 14
    usar_recubrimiento_etabs: bool = False
    forzar_fc: bool = False

    # Cortante sísmico
    usar_vc_cero_sismo: bool = True
    p_compresion_negativa: bool = True

    # Combinaciones
    norma_combinaciones: str = "usuario"   # "usuario" (1.25S) o "e060-2009" (1.0S)
    caso_muerta: str = ""
    caso_viva: str = ""
    casos_sismo: tuple[str, ...] = ()
    crear_combos_faltantes: bool = False
    analizar_si_crea: bool = False

    # Filtros ETABS
    vigas: tuple[str, ...] = ()
    secciones: tuple[str, ...] = ()
    pisos: tuple[str, ...] = ()
    max_vigas: int | None = None

    # Salida
    formatos: tuple[str, ...] = ("md", "docx")
    directorio_salida: str = "salidas"

    # Proyecto
    proyecto: str = "Proyecto estructural"
    ubicacion: str = "Perú"
    ingeniero: str = "Ingeniero estructural"
    cliente: str = ""
    revision: str = "A"

    def __post_init__(self) -> None:
        if self.fraccion_rho_b not in (0.5, 0.75):
            raise ValueError(
                "fraccion_rho_b debe ser 0.50 o 0.75 (criterio clásico "
                "0.50ρb / 0.75ρb de la E.060)."
            )
        if self.norma_combinaciones.lower() not in {"usuario", "e060-2009"}:
            raise ValueError("norma_combinaciones debe ser 'usuario' o 'e060-2009'.")
        if self.max_capas not in (1, 2, 3):
            raise ValueError("max_capas debe ser 1, 2 o 3.")
        if self.fc_default <= 0 or self.fy_default <= 0 or self.fyt_default <= 0:
            raise ValueError("f'c, fy y fyt deben ser positivos.")
        if self.recubrimiento_libre_cm < 0:
            raise ValueError("El recubrimiento no puede ser negativo.")
        if self.max_vigas is not None and self.max_vigas < 0:
            raise ValueError("max_vigas no puede ser negativo.")
        formatos = tuple(f.lower() for f in self.formatos)
        for f in formatos:
            if f not in {"md", "docx"}:
                raise ValueError("Los formatos válidos son 'md' y 'docx'.")
        object.__setattr__(self, "formatos", formatos)

    @property
    def factor_sismo(self) -> float:
        """
        Factor de la acción sísmica en las combinaciones.

        El usuario pidió explícitamente U = 1.25(D+L) ± 1.25S y
        U = 0.9D ± 1.25S.  La edición 2009 de la E.060, artículo 9.2.3, se
        cita en muchas reproducciones con ±CS (factor 1.0), mientras que la
        edición 2006 y la práctica ACI usan ±1.25CS.  El programa permite
        ambas y documenta la seleccionada.
        """
        return 1.25 if self.norma_combinaciones.lower() == "usuario" else 1.0
