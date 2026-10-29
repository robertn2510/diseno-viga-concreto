"""
Pruebas del motor de diseño E.060.

Ejecución:
    python -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from e060 import normas, figuras, memoria, servicio, unidades
from e060.columna import (DemandaColumna, EntradaColumna, LayoutBarras,
                          disenar_columna)
from e060.etabs import ETABSDemo, ETABSTablas
from e060.seccion import Seccion, area_acero_requerida, area_centroide, rectangulo
from e060.viga import (DemandaViga, EntradaViga, barras_por_capa, disenar_corte,
                       disenar_viga, seleccionar_refuerzo)

EJEMPLOS = os.path.join(RAIZ, "ejemplos")


# ===========================================================================
class TestMateriales(unittest.TestCase):

    def test_beta1(self):
        self.assertAlmostEqual(normas.beta1(210), 0.85)
        self.assertAlmostEqual(normas.beta1(280), 0.85)
        self.assertAlmostEqual(normas.beta1(350), 0.85 - 0.05 * 70 / 70)
        self.assertAlmostEqual(normas.beta1(420), 0.85 - 0.05 * 140 / 70, places=6)
        self.assertAlmostEqual(normas.beta1(700), 0.65)

    def test_modulo_elasticidad(self):
        self.assertAlmostEqual(normas.modulo_elasticidad_concreto(210),
                               15000 * math.sqrt(210), places=3)

    def test_phi_transicion(self):
        self.assertAlmostEqual(normas.phi_flexion(0.001), 0.65)
        self.assertAlmostEqual(normas.phi_flexion(0.007), 0.90)
        self.assertTrue(0.65 < normas.phi_flexion(0.0035) < 0.90)

    def test_acero_minimo(self):
        b, d, fc, fy = 30.0, 55.0, 210.0, 4200.0
        esperado = max(0.25 * math.sqrt(fc) / fy, 14.0 / fy) * b * d
        self.assertAlmostEqual(normas.acero_minimo_flexion(b, d, fc, fy), esperado)


class TestUnidades(unittest.TestCase):

    def test_fuerza(self):
        self.assertAlmostEqual(unidades.fuerza_a_kgf(1.0, "tonf"), 1000.0)
        self.assertAlmostEqual(unidades.fuerza_a_kgf(1.0, "kN"), 101.9716, places=3)

    def test_longitud(self):
        self.assertAlmostEqual(unidades.longitud_a_cm(1.0, "m"), 100.0)
        self.assertAlmostEqual(unidades.longitud_a_cm(1.0, "in"), 2.54)

    def test_sistema(self):
        s = unidades.sistema_unidades("tonf_m_C")
        self.assertAlmostEqual(s.momento_a_kgfcm(1.0), 1.0e5)
        self.assertAlmostEqual(s.fuerza_a_kgf(1.0), 1000.0)
        s2 = unidades.sistema_unidades("kN-mm")
        self.assertAlmostEqual(s2.longitud_a_cm(1.0), 0.1)


class TestGeometria(unittest.TestCase):

    def test_area_centroide(self):
        a, cx, cy = area_centroide(rectangulo(30, 60))
        self.assertAlmostEqual(a, 1800.0)
        self.assertAlmostEqual(cx, 0.0, places=9)
        self.assertAlmostEqual(cy, 0.0, places=9)

    def test_inercia(self):
        barras = LayoutBarras(3, 3, 1.905).posiciones(40, 40)
        sec = Seccion(40, 40, barras, 210, 4200)
        self.assertAlmostEqual(sec.Ix, 40 * 40 ** 3 / 12.0, delta=1.0)


class TestSeccionColumna(unittest.TestCase):

    def setUp(self):
        barras = LayoutBarras(3, 3, 1.905, 0.953, 4.0).posiciones(40, 40)
        self.sec = Seccion(40, 40, barras, 210, 4200)

    def test_p0(self):
        as_total = self.sec.As_total
        esperado = 0.85 * 210 * (1600 - as_total) + 4200 * as_total
        self.assertAlmostEqual(self.sec.P0, esperado, delta=1.0)

    def test_phi_pn_max(self):
        self.assertAlmostEqual(self.sec.phiPn_max(), 0.65 * 0.80 * self.sec.P0, delta=1.0)

    def test_capacidad_crece_con_axial_y_luego_cae(self):
        m0, _ = self.sec.capacidad_uniaxial(90.0, 0.0)
        m50, _ = self.sec.capacidad_uniaxial(90.0, 50e3)
        m150, _ = self.sec.capacidad_uniaxial(90.0, 150e3)
        self.assertGreater(m50, m0)          # zona controlada por compresión
        self.assertGreater(m0, m150)         # se reduce al acercarse a φPn,max

    def test_biaxial_igual_a_uniaxial_en_eje(self):
        m_uni, _ = self.sec.capacidad_uniaxial(90.0, 100e3)
        m_bia, _ = self.sec.capacidad_biaxial(100e3, 90.0)
        self.assertAlmostEqual(m_uni, m_bia, delta=0.02 * m_uni)

    def test_simetria_biaxial(self):
        m45, _ = self.sec.capacidad_biaxial(100e3, 45.0)
        m225, _ = self.sec.capacidad_biaxial(100e3, 225.0)
        self.assertAlmostEqual(m45, m225, delta=0.03 * m45)


class TestViga(unittest.TestCase):

    def test_barra_por_capa(self):
        # b útil = 20.1 cm; con s_mín = 1.33·agregado = 2.66 cm caben 4 barras 3/4"
        self.assertEqual(barras_por_capa(30, 1.905, 4.0, 0.953), 4)
        self.assertEqual(barras_por_capa(30, 2.54, 4.0, 0.953), 3)

    def test_area_acero_requerida(self):
        mu = 20e5          # 20 t·m en kgf·cm
        as_req = area_acero_requerida(mu, 30, 54, 210, 4200)
        a = as_req * 4200 / (0.85 * 210 * 30)
        mn = as_req * 4200 * (54 - a / 2)
        self.assertAlmostEqual(0.9 * mn, mu, delta=1e-6 * mu)

    def test_seleccion_cumple_capacidad(self):
        op = seleccionar_refuerzo(25e5, 30, 60, 4.0, 0.953, 210, 4200)
        self.assertIsNotNone(op)
        self.assertGreaterEqual(op["phiMn"], 25e5)
        self.assertTrue(op["cumple_ductilidad"])

    def test_diseno_corte_sin_sismo(self):
        c = disenar_corte(15000, 30, 54, 210, 4200, 60, 1.905, sismico=False)
        self.assertGreater(c["s_adoptado"], 0)
        self.assertTrue(c["cumple_seccion"])
        self.assertAlmostEqual(c["phi"], 0.85)

    def test_viga_completa(self):
        entrada = EntradaViga(
            nombre="V-1", b=30, h=60, fc=210, fy=4200, L=600,
            estaciones=[DemandaViga("Extremo i", 0.0, 22e5, 20e3),
                        DemandaViga("Centro", 12e5, 0.0, 3e3)])
        res = disenar_viga(entrada)
        self.assertEqual(len(res["estaciones"]), 2)
        self.assertGreater(res["As_min_10_5_1"], 0)
        self.assertIsNotNone(res["corte"])
        for est in res["estaciones"]:
            for clave in ("positivo", "negativo"):
                op = est.get(clave)
                if op:
                    self.assertGreaterEqual(op["phiMn"], est["demandas"].Mu_pos if clave == "positivo"
                                            else est["demandas"].Mu_neg)


class TestColumna(unittest.TestCase):

    def test_diseno_basico(self):
        entrada = EntradaColumna(nombre="C-1", b=45, h=45, fc=210, fy=4200,
                                 Pu=110e3, Mux=10e5, Muy=2e5, L=320)
        res = disenar_columna(entrada)
        self.assertGreaterEqual(res["barras"]["n"], 4)
        self.assertGreaterEqual(res["barras"]["rho"], 0.01 - 1e-6)
        self.assertLessEqual(res["barras"]["rho"], 0.06 + 1e-6)
        self.assertLessEqual(res["dcr"], 1.0)
        self.assertTrue(all(v["cumple"] for v in res["verificaciones"]))

    def test_esbeltez(self):
        entrada = EntradaColumna(nombre="C-2", b=30, h=40, fc=210, fy=4200,
                                 Pu=80e3, Mux=15e5, L=600, amplificar=True)
        res = disenar_columna(entrada)
        self.assertTrue(res["esbeltez"]["esbelto"])
        # δns nunca es menor que 1.0 (E.060 10.10.7.1)
        self.assertGreaterEqual(res["esbeltez"]["delta_ns"], 1.0)
        self.assertGreaterEqual(res["delta"], 1.0)

    def test_confina(self):
        entrada = EntradaColumna(nombre="C-3", b=60, h=60, fc=280, fy=4200,
                                 Pu=400e3, Mux=30e5, L=320)
        res = disenar_columna(entrada)
        self.assertGreater(res["estribos"]["Ash_s"], 0)
        self.assertTrue(res["estribos"]["s_conf"] <= 10.0)

    def test_columna_fuerte(self):
        r = normas.area_zuncho(60, 60)
        self.assertAlmostEqual(r, 52 * 52)


class TestModeloDemo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fuente = ETABSDemo()

    def test_elementos(self):
        nombres = self.fuente.listar_elementos()
        self.assertEqual(len(nombres), 28)
        self.assertTrue(any(n.startswith("V") for n in nombres))
        self.assertTrue(any(n.startswith("C") for n in nombres))

    def test_diseno_de_todos_los_elementos(self):
        opc = servicio.OpcionesDiseno(n_estaciones=5)
        for nombre in self.fuente.listar_elementos():
            el = self.fuente.obtener_elemento(nombre)
            salida = servicio.disenar_elemento(el, opc)
            self.assertIn(salida["tipo"], ("Viga", "Columna"))
            self.assertTrue(servicio.verificar_resultado(salida))

    def test_equilibrio_envolvente(self):
        el = self.fuente.obtener_elemento("V4-2")
        envs = el.envolventes()
        m_max = max(e["Mu_pos"] for e in envs)
        self.assertGreater(m_max, 0)
        # el momento positivo en el centro debe superar al de los extremos
        centro = [e for e in envs if abs(e["estacion"] - el.L / 2) < 5][0]
        self.assertGreater(centro["Mu_pos"], 0.5 * m_max)


class TestTablas(unittest.TestCase):

    def test_importacion_ejemplo(self):
        ruta = os.path.join(EJEMPLOS, "ElementForces_Frames.csv")
        if not os.path.exists(ruta):
            self.skipTest("No están los archivos de ejemplo")
        fuente = ETABSTablas.desde_archivos(
            ruta,
            os.path.join(EJEMPLOS, "FrameSections_Rectangular.csv"),
            os.path.join(EJEMPLOS, "MaterialProperties_Concrete.csv"),
            tipo_defecto="auto")
        nombres = fuente.listar_elementos()
        self.assertEqual(len(nombres), 2)
        el = fuente.obtener_elemento("V1-2")
        self.assertAlmostEqual(el.b, 30.0, places=3)
        self.assertAlmostEqual(el.h, 60.0, places=3)
        self.assertAlmostEqual(el.fc, 210.0, delta=2)
        self.assertAlmostEqual(el.L, 600.0, delta=1)
        self.assertEqual(len(el.combos), 11)

    def test_diseno_desde_tablas(self):
        ruta = os.path.join(EJEMPLOS, "ElementForces_Frames.csv")
        if not os.path.exists(ruta):
            self.skipTest("No están los archivos de ejemplo")
        fuente = ETABSTablas.desde_archivos(
            ruta, os.path.join(EJEMPLOS, "FrameSections_Rectangular.csv"))
        for nombre in fuente.listar_elementos():
            salida = servicio.disenar_elemento(fuente.obtener_elemento(nombre),
                                               servicio.OpcionesDiseno())
            self.assertTrue(salida["resumen"])


class TestMemoria(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fuente = ETABSDemo()
        cls.viga = servicio.disenar_elemento(cls.fuente.obtener_elemento("V1-2"),
                                             servicio.OpcionesDiseno(proyecto="Prueba"))
        cls.columna = servicio.disenar_elemento(cls.fuente.obtener_elemento("C1-1"),
                                                servicio.OpcionesDiseno(proyecto="Prueba"))

    def test_memoria_viga(self):
        doc = memoria.construir_memoria(self.viga)
        html = doc.html()
        self.assertIn("MEMORIA DE CÁLCULO", html)
        self.assertIn("Diseño por flexión", html)
        self.assertIn("Diseño por corte", html)
        self.assertIn("erificaciones", html)
        self.assertGreater(len(html), 12000)

    def test_memoria_columna(self):
        doc = memoria.construir_memoria(self.columna)
        html = doc.html()
        self.assertIn("COLUMNA", html)
        self.assertIn("interacción", html.lower())
        self.assertIn("Confinamiento", html)

    def test_markdown(self):
        md = memoria.construir_memoria(self.viga).markdown()
        self.assertIn("# MEMORIA", md)
        self.assertIn("|", md)


class TestExportacionYpuente(unittest.TestCase):
    """Ida y vuelta: exportar tablas → reimportarlas → mismo diseño."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from e060.etabs.exportar import exportar_tablas
        cls.tmp = tempfile.mkdtemp(prefix="e060_puente_")
        cls.demo = ETABSDemo()
        cls.rutas = exportar_tablas(cls.demo, cls.tmp)

    def test_archivos_generados(self):
        for clave in ("fuerzas", "secciones", "materiales"):
            self.assertTrue(os.path.isfile(self.rutas[clave]), clave)
            minimo = 50 if clave == "materiales" else 200
            self.assertGreater(os.path.getsize(self.rutas[clave]), minimo)

    def test_reimportacion_coincide_con_el_modelo(self):
        fuente = ETABSTablas.desde_archivos(self.rutas["fuerzas"],
                                            self.rutas["secciones"],
                                            self.rutas["materiales"])
        nombres = fuente.listar_elementos()
        self.assertEqual(len(nombres), len(self.demo.listar_elementos()))
        for n in nombres:
            a, b = fuente.obtener_elemento(n), self.demo.obtener_elemento(n)
            self.assertAlmostEqual(a.b, b.b, places=6)
            self.assertAlmostEqual(a.h, b.h, places=6)
            self.assertAlmostEqual(a.fc, b.fc, places=6)
            self.assertAlmostEqual(a.L, b.L, delta=1.0)
            self.assertEqual(a.tipo, b.tipo)
            self.assertEqual(len(a.combos), len(b.combos))

    def test_diseno_identico_tras_el_viaje(self):
        fuente = ETABSTablas.desde_archivos(self.rutas["fuerzas"],
                                            self.rutas["secciones"],
                                            self.rutas["materiales"])
        for nombre in ("V1-2", "C1-1"):
            a = servicio.disenar_elemento(fuente.obtener_elemento(nombre),
                                          servicio.OpcionesDiseno())
            b = servicio.disenar_elemento(self.demo.obtener_elemento(nombre),
                                          servicio.OpcionesDiseno())
            self.assertEqual(a["tipo"], b["tipo"])
            if a["tipo"] == "Viga":
                ra, rb = a["resumen"], b["resumen"]
                self.assertAlmostEqual(ra["corte_gobernante"]["s_conf"],
                                       rb["corte_gobernante"]["s_conf"], places=3)
                for fa, fb in zip(ra["filas"], rb["filas"]):
                    self.assertAlmostEqual(fa["phiMn_pos"], fb["phiMn_pos"], places=2)
            else:
                self.assertAlmostEqual(a["resumen"]["dcr"], b["resumen"]["dcr"],
                                       places=3)

    def test_fc_por_material_en_tablas(self):
        """f'c se toma del material de la sección, no de un valor fijo."""
        fuente = ETABSTablas.desde_archivos(self.rutas["fuerzas"],
                                            self.rutas["secciones"],
                                            self.rutas["materiales"])
        for n in fuente.listar_elementos():
            self.assertAlmostEqual(fuente.obtener_elemento(n).fc, 210.0, places=6)


class TestConexionETABS(unittest.TestCase):
    """Diagnóstico de la conexión COM/OAPI (sin ETABS en el entorno de prueba)."""

    def test_diagnostico_estructura(self):
        from e060.etabs import com
        d = com.diagnostico_com()
        for clave in ("plataforma", "es_windows", "com_disponible", "motivo",
                      "sugerencias"):
            self.assertIn(clave, d)
        self.assertIsInstance(d["sugerencias"], list)

    def test_error_con_sugerencias(self):
        from e060.etabs import com
        if com.diagnostico_com()["com_disponible"]:
            self.skipTest("Hay COM disponible: la conexión sí es posible")
        with self.assertRaises(com.ConexionETABSError) as ctx:
            com.conectar()
        err = ctx.exception
        self.assertIn(err.codigo, ("plataforma", "sin_com", "etabs_cerrado"))
        datos = err.to_dict()
        self.assertFalse(datos["ok"])
        self.assertTrue(datos["error"])
        self.assertTrue(datos["sugerencias"])


class TestFiguras(unittest.TestCase):

    @staticmethod
    def _valido(svg: str):
        import xml.dom.minidom
        xml.dom.minidom.parseString(svg)

    def test_svg_seccion(self):
        svg = figuras.svg_seccion(30, 60, 4.0, 0.953,
                                  [(-9, -25, 1.905), (9, 25, 1.905)])
        self.assertIn("<svg", svg)
        self._valido(svg)

    def test_svg_interaccion(self):
        inter = figuras.svg_interaccion([(100, 5.0), (50, 10.0), (0, 2.0)],
                                        [(80, 6.0, "C1")])
        self._valido(inter)

    def test_svg_envolvente(self):
        env = figuras.svg_envolvente(
            [{"estacion": 0, "Mu_pos": 0, "Mu_neg": 20e5},
             {"estacion": 300, "Mu_pos": 12e5, "Mu_neg": 0}], 600)
        self._valido(env)

    def test_svg_estribos(self):
        self._valido(figuras.svg_estribos(600, 120, 10, 20, 30, 60))


class TestSeccionAvanzada(unittest.TestCase):
    """Validaciones numéricas independientes de la sección."""

    def setUp(self):
        from e060.columna import construye_seccion
        self.sec = construye_seccion(40, 40, LayoutBarras(3, 3, 1.905, 0.953, 4.0),
                                     210, 4200)

    def test_equilibrio_integracion_independiente(self):
        """P y M de una fibra se comparan con una integración por franjas."""
        fc, fy, Es, ecu = 210.0, 4200.0, 2.04e6, 0.003
        b = h = 40.0
        N = 2000
        dA = b * h / N
        for c in (6.0, 12.0, 24.0):
            a = normas.beta1(fc) * c
            P = 0.0
            M = 0.0
            for i in range(N):
                y = -h / 2 + h * (i + 0.5) / N
                d = y + h / 2.0                    # distancia desde la fibra comprimida
                if d <= a:
                    P += 0.85 * fc * dA
                    M += -0.85 * fc * dA * y
            for br in self.sec.barras:
                d = br.y + h / 2.0
                eps = ecu * (c - d) / c
                fs = max(-fy, min(fy, Es * eps))
                F = fs * br.area
                if eps > 0:
                    F -= 0.85 * fc * br.area
                P += F
                M += -F * br.y
            fb = self.sec.fibra(c, 90.0)
            self.assertAlmostEqual(fb.P, P, delta=0.01 * abs(P))
            self.assertAlmostEqual(fb.Mx, M, delta=0.02 * abs(M))

    def test_biaxial_coincide_con_uniaxial(self):
        for pu in (0.0, 50_000.0, 120_000.0):
            uni, _ = self.sec.capacidad_uniaxial(90.0, pu)
            biax, _ = self.sec.capacidad_biaxial(pu, 0.0)
            self.assertAlmostEqual(biax / uni, 1.0, places=2)

    def test_biaxial_menor_que_uniaxial_en_diagonal(self):
        pu = 80_000.0
        uni, _ = self.sec.capacidad_uniaxial(90.0, pu)
        dia, _ = self.sec.capacidad_biaxial(pu, 45.0)
        self.assertLess(dia, uni)
        self.assertGreater(dia, 0.6 * uni)

    def test_contorno_biaxial_cerrado(self):
        pts = self.sec.contorno_biaxial(60_000.0, n=5)
        self.assertEqual(len(pts), 5)
        self.assertGreater(pts[0][0], 0)
        self.assertGreater(pts[-1][1], 0)

    def test_phiPn_max(self):
        self.assertAlmostEqual(self.sec.phiPn_max(), 0.65 * 0.8 * self.sec.P0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
