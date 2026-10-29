"""
Servidor web local (solo biblioteca estándar) para el sistema de diseño E.060.

Ejecución
---------
    python servidor.py                 # http://localhost:8000
    python servidor.py --puerto 8000 --host 0.0.0.0

Expone una API JSON y la interfaz web de `web/index.html`. No requiere
dependencias externas: pensado para funcionar en Windows junto a ETABS y en
cualquier equipo para revisar memorias.
"""

from __future__ import annotations

import argparse
import email
import json
import mimetypes
import os
import re
import sys
import tempfile
import threading
import zipfile
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from urllib.parse import parse_qs, urlparse

RAIZ = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(RAIZ, "web")
SALIDAS = os.path.join(RAIZ, "salidas")

from e060 import __version__, servicio                      # noqa: E402
from e060.etabs.com import diagnostico_com as diagnostico_etabs  # noqa: E402
from e060.memoria import construir_memoria, guardar_pdf    # noqa: E402
from e060.unidades import sistema_unidades                  # noqa: E402


# ===========================================================================
# Registro de fuentes de datos
# ===========================================================================
class Registro:
    def __init__(self):
        self.fuentes: dict = {}
        self.memorias: dict = {}
        self.lock = threading.Lock()
        self._demo = None

    def demo(self):
        if self._demo is None:
            from e060.etabs import ETABSDemo
            self._demo = ETABSDemo()
            self.fuentes["demo"] = self._demo
        return self._demo

    def obtener(self, ident: str):
        if ident in self.fuentes:
            return self.fuentes[ident]
        if ident == "demo":
            return self.demo()
        raise KeyError(f"Fuente desconocida: {ident}")

    def listar(self):
        self.demo()
        salida = []
        for ident, f in self.fuentes.items():
            if ident == "etabs":
                # la conexión COM se informa abajo con su diagnóstico completo
                # (evita duplicar la tarjeta en la interfaz)
                continue
            salida.append({
                "id": ident,
                "nombre": getattr(f, "nombre", ident),
                "descripcion": getattr(f, "descripcion", ""),
                "info": f.info_modelo() if hasattr(f, "info_modelo") else {},
            })
        # ETABS COM: se informa si es posible en este equipo (solo Windows)
        from e060.etabs.com import diagnostico_com
        diag = diagnostico_com()
        conectado = "etabs" in self.fuentes
        salida.append({
            "id": "etabs",
            "nombre": "ETABS en ejecución (COM/OAPI)",
            "solo_seleccionados": bool(getattr(self.fuentes.get("etabs"),
                                               "_solo_seleccionados", False))
            if conectado else False,
            "descripcion": (
                "Conectado · usa los elementos seleccionados o todo el modelo"
                if conectado else
                ("Conecta con ETABS v20–v23 abierto y usa los elementos "
                 "seleccionados o todo el modelo.")
                if diag["com_disponible"] else
                "Lee tu ETABS de Windows y lo envía a esta interfaz (puente "
                "en un clic, sin copiar archivos)."),
            "info": {"sistema": sys.platform},
            "disponible": bool(diag["com_disponible"]),
            "conectado": conectado,
            "motivo": "" if diag["com_disponible"] else diag["motivo"],
            "sugerencias": diag["sugerencias"] if not diag["com_disponible"] else [],
        })
        return salida

    def conectar_etabs(self, solo_seleccionados: bool = False):
        """Se engancha a ETABS; si ya estaba conectado, solo recarga las tablas."""
        from e060.etabs import conectar
        with self.lock:
            f = self.fuentes.get("etabs")
            if f is None:
                f = conectar(adjuntar=True, solo_seleccionados=solo_seleccionados)
                self.fuentes["etabs"] = f
            else:
                f.recargar(bool(solo_seleccionados))
        return f

    def agregar(self, fuente) -> str:
        ident = f"tabla-{uuid.uuid4().hex[:8]}"
        self.fuentes[ident] = fuente
        return ident

    def guardar_memoria(self, out: dict) -> str:
        ident = uuid.uuid4().hex[:12]
        with self.lock:
            self.memorias[ident] = out
        return ident


REGISTRO = Registro()


# ===========================================================================
# Helpers de respuesta
# ===========================================================================
def _json(handler, data, codigo=200):
    cuerpo = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(codigo)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(cuerpo)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(cuerpo)


def _html(handler, texto: str, codigo=200):
    cuerpo = texto.encode("utf-8")
    handler.send_response(codigo)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(cuerpo)))
    handler.end_headers()
    handler.wfile.write(cuerpo)


def _descargar(handler, datos: bytes, nombre: str, tipo: str):
    handler.send_response(200)
    handler.send_header("Content-Type", tipo)
    handler.send_header("Content-Disposition", f'attachment; filename="{nombre}"')
    handler.send_header("Content-Length", str(len(datos)))
    handler.end_headers()
    handler.wfile.write(datos)


def url_publica(handler) -> str:
    """
    URL con la que el navegador está viendo esta interfaz.

    Es la que debe usar el puente (`puente_etabs.py --subir …`) en la PC con
    ETABS, aunque la interfaz corra en otro equipo (Linux, contenedor, web).
    """
    host = (handler.headers.get("Host") or "localhost:8000").strip()
    proto = handler.headers.get("X-Forwarded-Proto")
    if not proto:
        proto = "https" if (host.endswith(".e2b.app") or host.endswith(".arena.ai")) \
            else "http"
    return f"{proto}://{host}"


def archivos_paquete(raiz: str = RAIZ):
    """
    Archivos que acompañan al puente: el paquete `e060` completo (son pocos
    módulos y sin dependencias externas) y el propio puente. Se recorre la
    carpeta para no olvidar ningún módulo si el paquete crece.
    """
    archivos = ["puente_etabs.py"]
    for base, carpetas, ficheros in os.walk(os.path.join(raiz, "e060")):
        carpetas[:] = [c for c in carpetas if c != "__pycache__"]
        for fichero in sorted(ficheros):
            if fichero.endswith(".py"):
                archivos.append(os.path.relpath(os.path.join(base, fichero), raiz)
                                .replace(os.sep, "/"))
    return archivos

_LEEME = """PUENTE ETABS -> INTERFAZ WEB  (Diseno E.060)
===========================================

Sirve para usar el ETABS de ESTA PC desde la interfaz web, aunque la interfaz
corra en otro equipo (Linux, contenedor o servidor).

PASOS
-----
1. Instale Python 3.8 o superior DE 64 BITS (python.org) y marque
   "Add Python to PATH" durante la instalacion.
2. Instale la libreria de automatizacion COM (una vez):
       pip install comtypes
3. Abra ETABS v20, v21, v22 o v23, cargue el modelo, desbloquee el modelo
   (Model > Unlock Model) y ejecute el analisis (Analyze > Run Analysis).
4. Seleccione en ETABS las vigas y/o columnas que quiera disenar.
5. Ejecute:
       SUBIR_seleccion.bat        (solo las barras seleccionadas)
   o bien
       SUBIR_todo.bat             (todo el modelo)
   Tambien puede ejecutar a mano:
       python puente_etabs.py --seleccionados --subir {url}

La interfaz mostrara automaticamente la fuente importada; elija el elemento y
pulse "Disenar segun E.060".

QUE HACE
--------
Lee las solicitaciones de ETABS (estaciones reales de la tabla
"Element Forces - Frames"), las escribe en CSV y las envia por HTTP a la
interfaz. No modifica el modelo.

SI ALGO FALLA
-------------
* "No se encontro una instancia de ETABS": ETABS debe estar ABIERTO.
* "No hay barras seleccionadas": seleccione barras o use SUBIR_todo.bat.
* "La tabla de fuerzas esta vacia": ejecute el analisis en ETABS.
* Error de conexion COM: use Python de 64 bits y "pip install comtypes".
"""


def construir_paquete_puente(url: str, raiz: str = RAIZ) -> bytes:
    """
    Paquete .zip para ejecutar el puente en el Windows con ETABS.

    Incluye el puente, los modulos que necesita, un LEEME y dos .bat con la
    dirección de esta interfaz ya escrita: el usuario solo descomprime y hace
    doble clic.
    """
    def bat(nombre: str, argumentos: str, titulo: str) -> bytes:
        lineas = [
            "@echo off",
            f"REM {titulo} - Diseno E.060",
            'cd /d "%~dp0"',
            f"title {titulo}",
            "where python >nul 2>nul",
            "if errorlevel 1 (",
            "  echo [ERROR] No se encontro Python en el PATH.",
            "  echo Instale Python 3.8+ de 64 bits desde python.org y marque",
            '  echo "Add Python to PATH".',
            "  pause",
            "  exit /b 1",
            ")",
            'python -c "import comtypes" >nul 2>nul',
            "if errorlevel 1 (",
            "  echo [AVISO] Falta comtypes. Instalando...",
            "  python -m pip install comtypes",
            ")",
            f"python puente_etabs.py {argumentos}",
            "echo.",
            "pause",
        ]
        return ("\r\n".join(lineas) + "\r\n").encode("ascii", "replace")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for relativo in archivos_paquete(raiz):
            ruta = os.path.join(raiz, relativo)
            if os.path.isfile(ruta):
                with open(ruta, "rb") as fh:
                    z.writestr(relativo, fh.read())
        z.writestr("LEEME.txt", _LEEME.format(url=url).encode("utf-8"))
        z.writestr("SUBIR_seleccion.bat",
                   bat("SUBIR_seleccion", f"--seleccionados --subir \"{url}\"",
                       "Puente ETABS - barras seleccionadas"))
        z.writestr("SUBIR_todo.bat",
                   bat("SUBIR_todo", f"--subir \"{url}\"",
                       "Puente ETABS - todo el modelo"))
    return buffer.getvalue()


def _opciones(datos: dict) -> servicio.OpcionesDiseno:
    opc = servicio.OpcionesDiseno()
    for campo in ("tipo", "sismico", "recubrimiento", "db_estribo", "n_estaciones",
                  "considerar_torsion", "amplificar_esbeltez", "beta_dns",
                  "varilla_pref", "b", "h", "fc", "fy", "luz_libre",
                  "usar_vc_nulo_sismo", "proyecto", "ubicacion", "autor",
                  "norma_sismo", "notas"):
        if campo in datos and datos[campo] not in (None, ""):
            try:
                setattr(opc, campo, datos[campo])
            except Exception:
                pass
    for campo_num in ("recubrimiento", "b", "h", "fc", "fy", "luz_libre", "n_estaciones"):
        v = getattr(opc, campo_num, None)
        if v not in (None, ""):
            try:
                setattr(opc, campo_num, float(v))
            except (TypeError, ValueError):
                setattr(opc, campo_num, None if campo_num != "n_estaciones" else 5)
    opc.n_estaciones = int(opc.n_estaciones or 5)
    return opc


# ===========================================================================
# Serialización de resultados
# ===========================================================================
def serie_elemento(fuente_id: str, nombre: str) -> dict:
    fuente = REGISTRO.obtener(fuente_id)
    el = fuente.obtener_elemento(nombre)
    envs = el.envolventes()
    return {
        "nombre": el.nombre, "tipo": el.tipo, "story": el.story,
        "seccion": el.seccion, "b": el.b, "h": el.h, "fc": el.fc, "fy": el.fy,
        "L": el.L, "origen": el.origen, "combos": el.combos,
        "unidad_fuerza": el.unidad_fuerza, "unidad_longitud": el.unidad_longitud,
        "resumen": el.resumen(),
        "envolventes": [{
            "estacion": e["estacion"],
            "Mu_pos": e["Mu_pos"] / 1e5, "Mu_neg": -e["Mu_neg"] / 1e5,
            "Vu": e["Vu"] / 1e3, "Tu": e["Tu"] / 1e5, "Pu": e["Pu"] / 1e3,
            "combo_pos": e["combo_pos"], "combo_neg": e["combo_neg"],
        } for e in envs],
        "puntos": [{"combo": p.combo, "x": p.estacion, "P": p.P / 1e3,
                    "V2": p.V2 / 1e3, "M3": p.M3 / 1e5, "M2": p.M2 / 1e5,
                    "T": p.T / 1e5} for p in el.puntos][:3000],
    }


def serializar_salida(out: dict, memoria_id: str) -> dict:
    r = out["resumen"]
    el = out["elemento"]
    base = {
        "ok": True, "memoria_id": memoria_id, "tipo": out["tipo"],
        "elemento": {"nombre": el.nombre, "story": el.story, "b": el.b,
                     "h": el.h, "fc": el.fc, "fy": el.fy, "L": el.L},
        "verificaciones": servicio.verificar_resultado(out),
        "aprobado": servicio.aprobado(out),
        "fecha": out["fecha"],
    }
    if out["tipo"] == "Viga":
        corte = r["corte_gobernante"] or {}
        from e060.viga import posiciones_longitudinales
        rec = getattr(out.get("opciones"), "recubrimiento", 4.0)
        ests = out["resultado"]["estaciones"]
        est_pos = max(ests, key=lambda e: (e.get("positivo") or {}).get("area", 0.0))
        est_neg = max(ests, key=lambda e: (e.get("negativo") or {}).get("area", 0.0))
        barras = posiciones_longitudinales(est_pos.get("positivo"), el.b, el.h,
                                           rec, 0.953, "inferior")
        barras += posiciones_longitudinales(est_neg.get("negativo"), el.b, el.h,
                                            rec, 0.953, "superior")
        base["vigas"] = {
            "barras": {
                "descripcion": "Inferior: %s · Superior: %s" % (
                    max(r["filas"], key=lambda f: f["As_pos"])["ref_pos"],
                    max(r["filas"], key=lambda f: f["As_neg"])["ref_neg"]),
                "db": max((op["db"] for est in ests
                           for op in (est.get("positivo"), est.get("negativo")) if op),
                          default=1.905),
                "posiciones": barras,
            },
            "filas": [{
                "estacion": f["estacion"],
                "Mu_pos": f["Mu_pos"], "Mu_neg": f["Mu_neg"],
                "As_pos": f["As_pos"], "As_neg": f["As_neg"],
                "ref_pos": f["ref_pos"], "ref_neg": f["ref_neg"],
                "phiMn_pos": f["phiMn_pos"], "phiMn_neg": f["phiMn_neg"],
                "dcr": max(f["dcr_pos"], f["dcr_neg"]),
                "Vu": f["Vu"],
            } for f in r["filas"]],
            "corte": {
                "estribo": corte.get("estribo"), "s_conf": corte.get("s_conf"),
                "s_resto": corte.get("s_resto"), "Vc": corte.get("Vc", 0) / 1e3,
                "Vu": corte.get("Vu", 0) / 1e3,
                "Vu_conf": corte.get("Vu_conf", 0) / 1e3,
                "phiVn": corte.get("phiVn", 0) / 1e3,
                "dcr": corte.get("dcr"), "phi": corte.get("phi"),
                "vc_cero": corte.get("vc_cero"),
                "ramas": corte.get("estribo_ramas"),
                "Av": corte.get("Av"),
            },
    }
    else:
        base["columnas"] = {
            "refuerzo": r["refuerzo"], "As": r["As"], "rho": r["rho"],
            "dcr": r["dcr"], "estribos": r["estribos"],
            "s_ext": r["s_ext"], "esbeltez": r["esbeltez"],
            "P0": r["P0"], "phiPn_max": r["phiPn_max"],
            "Pu": r["Pu"], "Mux": r["Mux"] / 1e5, "Muy": r["Muy"] / 1e5,
            "barras": out["resultado"]["barras"],
            "diagramas": out["resultado"]["diagramas"],
            "demandas": [{"combo": d.combo, "P": d.P / 1e3, "M2": d.M2 / 1e5,
                          "M3": d.M3 / 1e5} for d in out["entrada"].demandas],
        }
    return base


# ===========================================================================
# Manejo de peticiones
# ===========================================================================
class Handler(BaseHTTPRequestHandler):
    server_version = f"DisenoE060/{__version__}"

    # ------------------------------------------------------------------
    def log_message(self, fmt, *args):        # silencioso y compacto
        if os.environ.get("E060_DEBUG"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _leer_cuerpo(self) -> bytes:
        largo = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(largo) if largo else b""

    def _json_cuerpo(self) -> dict:
        crudo = self._leer_cuerpo()
        if not crudo:
            return {}
        try:
            return json.loads(crudo.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _multipart(self) -> dict:
        """Extrae archivos y campos de un formulario multipart."""
        tipo = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in tipo:
            return {}
        cuerpo = self._leer_cuerpo()
        msg = email.message_from_bytes(
            b"Content-Type: " + tipo.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + cuerpo)
        datos = {}
        for parte in msg.walk():
            if parte.get_content_maintype() == "multipart":
                continue
            nombre = parte.get_param("name", header="content-disposition")
            if not nombre:
                continue
            contenido = parte.get_payload(decode=True) or b""
            archivo = parte.get_filename()
            if archivo:
                datos.setdefault("archivos", {})[nombre] = (archivo, contenido)
            else:
                datos[nombre] = contenido.decode("utf-8", "replace")
        return datos

    # ------------------------------------------------------------------
    def do_GET(self):
        url = urlparse(self.path)
        ruta = url.path
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if ruta in ("/", "/index.html"):
                return self._estatico("index.html")
            if ruta.startswith("/web/"):
                return self._estatico(ruta[5:])
            if ruta == "/api/estado":
                from e060.etabs.com import diagnostico_com
                return _json(self, {
                    "version": __version__,
                    "norma": "NTP E.060 Concreto Armado (RNE) + E.030-2018",
                    "fuentes": REGISTRO.listar(),
                    "sistema": sys.platform,
                    "etabs": diagnostico_com(),
                })
            if ruta == "/api/puente":
                url = url_publica(self)
                diag = diagnostico_etabs()
                fuentes = [i for i in REGISTRO.fuentes if i != "etabs"]
                return _json(self, {
                    "ok": True,
                    "url": url,
                    "comando": f'python puente_etabs.py --seleccionados --subir "{url}"',
                    "comando_todo": f'python puente_etabs.py --subir "{url}"',
                    "descarga": "/descargas/puente.zip",
                    "es_windows": diag["es_windows"],
                    "com_disponible": diag["com_disponible"],
                    "fuentes": fuentes,
                    "instrucciones": [
                        "En la PC con ETABS: instale Python 3.8+ de 64 bits y "
                        "ejecute  pip install comtypes",
                        "Abra ETABS con el modelo, desbloquee y ejecute el "
                        "análisis; seleccione las barras a diseñar",
                        "Descargue el puente, descomprímalo y ejecute "
                        "SUBIR_seleccion.bat (o SUBIR_todo.bat)",
                    ],
                })
            if ruta == "/descargas/puente.zip":
                datos = construir_paquete_puente(url_publica(self))
                return _descargar(self, datos, "puente_etabs.zip",
                                  "application/zip")
            if ruta == "/api/elementos":
                fuente_id = q.get("fuente", "demo")
                fuente = REGISTRO.obtener(fuente_id)
                tipo = q.get("tipo", "Todos")
                texto = q.get("texto", "")
                if fuente_id == "etabs" and not isinstance(fuente, type(None)):
                    pass
                nombres = fuente.listar_elementos(tipo=tipo)
                salida = []
                for n in nombres:
                    try:
                        el = fuente.obtener_elemento(n)
                    except Exception:
                        continue
                    if texto and texto.lower() not in (n + el.seccion + el.story).lower():
                        continue
                    salida.append({"nombre": n, "tipo": el.tipo, "story": el.story,
                                   "seccion": el.seccion, "b": el.b, "h": el.h,
                                   "L": el.L, "combos": len(el.combos)})
                return _json(self, {"elementos": salida,
                                    "total": len(salida)})
            if ruta == "/api/elemento":
                fuente_id = q.get("fuente", "demo")
                return _json(self, serie_elemento(fuente_id, q["nombre"]))
            if ruta.startswith("/memoria/"):
                resto = ruta[len("/memoria/"):]
                ident = resto.split("/")[0]
                out = REGISTRO.memorias.get(ident)
                if not out:
                    return _html(self, "<h1>Memoria no encontrada</h1>", 404)
                doc = construir_memoria(out)
                if resto.endswith("/pdf"):
                    os.makedirs(SALIDAS, exist_ok=True)
                    tmp = os.path.join(SALIDAS, f"memoria_{ident}.pdf")
                    if guardar_pdf(out, tmp):
                        with open(tmp, "rb") as fh:
                            return _descargar(self, fh.read(),
                                              f"memoria_{out['elemento'].nombre}.pdf",
                                              "application/pdf")
                    return _html(self,
                                 "<h2>PDF no disponible</h2><p>Instale reportlab "
                                 "(pip install reportlab) para exportar en PDF, o use la "
                                 "impresión del navegador sobre la memoria HTML.</p>", 501)
                if resto.endswith("/md"):
                    texto = doc.markdown().encode("utf-8")
                    return _descargar(self, texto,
                                      f"memoria_{out['elemento'].nombre}.md",
                                      "text/markdown; charset=utf-8")
                if resto.endswith("/html"):
                    return _descargar(self, doc.html().encode("utf-8"),
                                      f"memoria_{out['elemento'].nombre}.html",
                                      "application/octet-stream")
                return _html(self, doc.html())
            return _json(self, {"error": "Ruta no encontrada"}, 404)
        except Exception as exc:                     # noqa: BLE001
            if os.environ.get("E060_DEBUG"):
                traceback.print_exc()
            return _json(self, {"error": str(exc)}, 400)

    # ------------------------------------------------------------------
    def do_POST(self):
        url = urlparse(self.path)
        ruta = url.path
        try:
            if ruta == "/api/disenar":
                datos = self._json_cuerpo()
                fuente_id = datos.get("fuente", "demo")
                fuente = REGISTRO.obtener(fuente_id)
                el = fuente.obtener_elemento(datos["nombre"])
                opc = _opciones(datos.get("opciones", {}))
                out = servicio.disenar_elemento(el, opc)
                ident = REGISTRO.guardar_memoria(out)
                return _json(self, serializar_salida(out, ident))
            if ruta == "/api/importar":
                datos = self._multipart()
                archivos = datos.get("archivos", {})
                if "fuerzas" not in archivos:
                    return _json(self, {"error": "Adjunte el archivo de fuerzas "
                                                 "(Element Forces - Frames)."}, 400)
                from e060.etabs import ETABSTablas
                os.makedirs(os.path.join(SALIDAS, "importados"), exist_ok=True)
                rutas = {}
                for clave, (nombre, contenido) in archivos.items():
                    destino = os.path.join(SALIDAS, "importados", f"{uuid.uuid4().hex[:6]}_{nombre}")
                    with open(destino, "wb") as fh:
                        fh.write(contenido)
                    rutas[clave] = destino
                fuente = ETABSTablas.desde_archivos(
                    rutas["fuerzas"], rutas.get("secciones"), rutas.get("materiales"),
                    unidades=datos.get("unidades") or None,
                    tipo_defecto=datos.get("tipo_defecto") or "auto")
                if datos.get("b") and datos.get("h"):
                    fuente.aplicar_dimensiones(float(datos.get("b")),
                                               float(datos.get("h")),
                                               float(datos.get("fc") or 210),
                                               float(datos.get("fy") or 4200))
                ident = REGISTRO.agregar(fuente)
                return _json(self, {"ok": True, "fuente_id": ident,
                                    "info": fuente.info_modelo(),
                                    "combos": fuente.listar_combos()[:50]})
            if ruta in ("/api/conectar-etabs", "/api/recargar-etabs"):
                from e060.etabs.com import ConexionETABSError, diagnostico_com
                diag = diagnostico_com()
                if not diag["com_disponible"]:
                    diag = dict(diag, ok=False, error=diag["motivo"],
                                codigo=("plataforma" if not diag["es_windows"]
                                        else "sin_com"))
                    return _json(self, diag, 409)
                datos = self._json_cuerpo()
                solo = bool(datos.get("solo_seleccionados", False))
                if ruta == "/api/recargar-etabs" and "etabs" not in REGISTRO.fuentes:
                    return _json(self, {"ok": False, "codigo": "sin_conexion",
                                        "error": "Aún no hay conexión con ETABS. "
                                                 "Pulse primero «Conectar».",
                                        "sugerencias": [
                                            "Abra ETABS con el modelo analizado y "
                                            "pulse «Conectar»."]}, 409)
                try:
                    fuente = REGISTRO.conectar_etabs(solo_seleccionados=solo)
                except ConexionETABSError as exc:
                    if ruta == "/api/recargar-etabs":
                        # una recarga fallida invalida la fuente anterior
                        REGISTRO.fuentes.pop("etabs", None)
                    return _json(self, exc.to_dict(), 409)
                actual = REGISTRO.obtener("etabs")
                return _json(self, {"ok": True, "fuente_id": "etabs",
                                    "solo_seleccionados": solo,
                                    "elementos": len(actual.listar_elementos()),
                                    "info": fuente.info_modelo()})
            return _json(self, {"error": "Ruta no encontrada"}, 404)
        except Exception as exc:                     # noqa: BLE001
            if os.environ.get("E060_DEBUG"):
                traceback.print_exc()
            return _json(self, {"error": str(exc)}, 400)

    # ------------------------------------------------------------------
    def _estatico(self, relativo: str):
        ruta = os.path.normpath(os.path.join(WEB, relativo))
        if not ruta.startswith(WEB) or not os.path.isfile(ruta):
            return _json(self, {"error": "Archivo no encontrado"}, 404)
        tipo = mimetypes.guess_type(ruta)[0] or "application/octet-stream"
        with open(ruta, "rb") as fh:
            datos = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)


def main():
    ap = argparse.ArgumentParser(description="Servidor del sistema de diseño E.060")
    ap.add_argument("--puerto", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    REGISTRO.demo()
    servidor = ThreadingHTTPServer((args.host, args.puerto), Handler)
    print(f" Diseño E.060 + ETABS v{__version__}")
    print(f" Servidor en http://{args.host}:{args.puerto}  (Ctrl+C para detener)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n Servidor detenido.")


if __name__ == "__main__":
    main()
