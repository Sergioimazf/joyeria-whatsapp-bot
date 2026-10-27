"""Pruebas de integración locales: app real, Dolibarr/Neon simulados.

Ninguna llamada accede a servicios externos ni usa credenciales.
"""
import unittest
from unittest.mock import patch

import app
import carrito_flujo


CATALOGO_SIMULADO = [
    {"label": "CAJA CHICA PARA ANILLO AZUL NAVY", "ref": "1481.NB"},
    {"label": "CAJA CHICA PARA ANILLO ROSA", "ref": "1481.PK"},
    {"label": "CAJA PARA COLLAR NEGRA", "ref": "3020.NG"},
    {"label": "CAJA PARA COLLAR BLANCA", "ref": "3020.BC"},
]


def buscar_simulado(terminos=None, limite=10):
    if not terminos:
        return CATALOGO_SIMULADO[:limite]
    return [
        p for p in CATALOGO_SIMULADO
        if all(t in (p["label"] + " " + p["ref"]).lower() for t in terminos)
    ][:limite]


class AplicacionCarritoTests(unittest.TestCase):
    def setUp(self):
        carrito_flujo.SESIONES.clear()
        app.COTIZACIONES.clear()
        self.folios_guardados = []
        self.patches = [
            patch.object(app, "CARRITO_MULTIPRODUCTO", True),
            patch.object(app, "buscar_productos", side_effect=buscar_simulado),
            patch.object(app, "almacenamiento_configurado", return_value=True),
            patch.object(app, "guardar_solicitud_multiple", side_effect=self.guardar),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def guardar(self, items, ciudad, sender):
        self.folios_guardados.append({
            "items": [item.copy() for item in items],
            "ciudad": ciudad,
            "sender": sender,
        })
        return "CAR-PRUEBA-20261027-01"

    def mensaje(self, texto):
        return app.preparar_respuesta(texto, sender="5218123456789")

    def test_flujo_varios_productos_desde_app(self):
        primero = self.mensaje("quiero cotizar 100 cajas para anillos y 20 cajas para collares")
        self.assertIn("1481.NB", primero)
        segundo = self.mensaje("1")
        self.assertIn("3020.NG", segundo)
        carrito = self.mensaje("1")
        self.assertIn("100 piezas", carrito)
        self.assertIn("20 piezas", carrito)
        cambiado = self.mensaje("CAMBIAR 2 37")
        self.assertIn("37 piezas", cambiado)
        agregado = self.mensaje("AGREGAR 50 1481.NB")
        self.assertIn("150 piezas", agregado)
        revisado = self.mensaje("VER")
        self.assertIn("150 piezas", revisado)
        self.assertIn("37 piezas", revisado)
        removido = self.mensaje("QUITAR 2")
        self.assertIn("150 piezas", removido)
        self.assertNotIn("3020.NG", removido)
        self.mensaje("LISTO")
        resumen = self.mensaje("Monterrey")
        self.assertIn("CONFIRMAR", resumen)
        self.assertEqual(self.folios_guardados, [])
        final = self.mensaje("CONFIRMAR")
        self.assertIn("CAR-PRUEBA", final)
        self.assertEqual(len(self.folios_guardados), 1)
        self.assertEqual(self.folios_guardados[0]["items"][0]["cantidad"], 150)
        self.assertEqual(self.folios_guardados[0]["ciudad"], "Monterrey")
        self.mensaje("CONFIRMAR")
        self.assertEqual(len(self.folios_guardados), 1)

    def test_cotizar_generico_sin_busqueda_falsa(self):
        inicio = self.mensaje("COTIZAR")
        self.assertIn("¿Qué producto", inicio)
        siguiente = self.mensaje("cajas para anillos")
        self.assertIn("1481.NB", siguiente)
        self.assertFalse(self.folios_guardados)

    def test_modo_anterior_sigue_disponible(self):
        with patch.object(app, "CARRITO_MULTIPRODUCTO", False):
            respuesta = self.mensaje("COTIZAR")
        self.assertIn("¿Qué producto", respuesta)
        self.assertFalse(carrito_flujo.SESIONES)


if __name__ == "__main__":
    unittest.main()
