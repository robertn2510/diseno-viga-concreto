"""Pruebas de la memoria y de la interfaz de línea de comandos."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import hacer_conexion

from vigas_e060 import cli
from vigas_e060.demo import ejecutar_demo
from vigas_e060.etabs.api import ETABSError
from vigas_e060.reporte import generar_reporte


def test_demo_completa(tmp_path):
    resultados, salidas = ejecutar_demo(tmp_path, formatos=("md",))
    assert len(resultados) == 3
    assert all(r.cumple for r in resultados)
    ruta = Path(salidas["md"])
    assert ruta.exists()
    texto = ruta.read_text(encoding="utf-8")
    assert "MEMORIA DE CÁLCULO" in texto
    assert "ANEXO A. FORMULACIÓN Y REFERENCIAS" in texto
    assert "ANEXO C. REGISTRO DE OBSERVACIONES" in texto
    assert "E.060 21.5.4.1" in texto
    assert "1 @ 0.05" in texto
    assert "As teórico" in texto
    assert "acero colocado" in texto.lower() or "As colocado" in texto


def test_demo_docx(tmp_path):
    docx = pytest.importorskip("docx")
    _, salidas = ejecutar_demo(tmp_path, formatos=("docx",))
    ruta = Path(salidas["docx"])
    assert ruta.exists() and ruta.stat().st_size > 10_000
    doc = docx.Document(str(ruta))
    textos = [p.text for p in doc.paragraphs]
    assert any("MEMORIA DE CÁLCULO" in t for t in textos)
    assert len(doc.tables) > 10


def test_reporte_sin_formatos(tmp_path):
    from vigas_e060.modelos import MetadatosProyecto

    with pytest.raises(RuntimeError):
        generar_reporte([], MetadatosProyecto(), [], [], ruta_salida=tmp_path, formatos=())


def test_cli_demo(tmp_path, capsys):
    codigo = cli.main(["--demo", "--salida", str(tmp_path), "--formato", "md"])
    assert codigo == 0
    salida = capsys.readouterr().out
    assert "MODO DEMOSTRACIÓN" in salida
    assert "CUMPLE" in salida


def test_cli_listar(monkeypatch, capsys):
    monkeypatch.setattr(cli, "conectar_etabs", lambda **kw: hacer_conexion())
    codigo = cli.main(["--listar"])
    assert codigo == 0
    salida = capsys.readouterr().out
    assert "V-101" in salida


def test_cli_flujo_etabs_simulado(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "conectar_etabs", lambda **kw: hacer_conexion())
    codigo = cli.main([
        "--caso-muerta", "DEAD",
        "--caso-viva", "LIVE",
        "--caso-sismo", "SISMO",
        "--salida", str(tmp_path),
        "--formato", "md",
        "--proyecto", "Prueba simulada",
        "--max-vigas", "1",
    ])
    assert codigo == 0
    archivos = list(tmp_path.glob("*.md"))
    assert len(archivos) == 1
    texto = archivos[0].read_text(encoding="utf-8")
    assert "Prueba simulada" in texto
    assert "V-101" in texto
    assert "COINCIDE" in texto


def test_cli_error_conexion(monkeypatch, capsys):
    def falla(**kw):
        raise ETABSError("ETABS no disponible")

    monkeypatch.setattr(cli, "conectar_etabs", falla)
    codigo = cli.main([])
    assert codigo == 1
    assert "ERROR DE ETABS" in capsys.readouterr().out
