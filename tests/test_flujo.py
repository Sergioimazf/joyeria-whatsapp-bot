import unittest
import carrito_flujo
from carrito_flujo import manejar_carrito


CATALOGO = [
    {"label": "CAJA CHICA PARA ANILLO AZUL NAVY", "ref": "1481.NB"},
    {"label": "CAJA CHICA PARA ANILLO ROSA", "ref": "1481.PK"},
    {"label": "CAJA PARA COLLAR NEGRA", "ref": "3020.NG"},
    {"label": "CAJA PARA COLLAR BLANCA", "ref": "3020.BC"},
]


def buscar(terminos, limite=60):
    return [
        p for p in CATALOGO
        if all(t in (p["label"] + " " + p["ref"]).lower() for t in terminos)
    ][:limite]


class FlujoTests(unittest.TestCase):
    def setUp(self):
        carrito_flujo.SESIONES.clear()
        self.guardados = []
        self.db_listo = True

    def guardar(self, items, ciudad, numero):
        self.guardados.append((items.copy(), ciudad, numero))
        return "CAR-20261027-1234567890"

    def responder(self, mensaje):
        return manejar_carrito(
            "5218123456789", mensaje, buscar, carrito_flujo._terminos,
            self.guardar, lambda: self.db_listo
        )

    def test_cotizacion_de_dos_productos(self):
        r = self.responder("Quiero cotizar 100 cajas para anillos y 50 cajas para collares")
        self.assertIn("1481.NB", r)
        r = self.responder("1")
        self.assertIn("3020.NG", r)
        r = self.responder("1")
        self.assertIn("100 piezas", r)
        self.assertIn("50 piezas", r)
        self.responder("LISTO")
        r = self.responder("Guadalajara")
        self.assertIn("CONFIRMAR", r)
        self.assertEqual(self.guardados, [])
        r = self.responder("CONFIRMAR")
        self.assertIn("CAR-20261027-1234567890", r)
        self.assertEqual([i["cantidad"] for i in self.guardados[0][0]], [100, 50])

    def test_agregar_separadamente(self):
        self.responder("cotizar 100 1481.NB")
        r = self.responder("AGREGAR 50 cajas para collares")
        self.assertIn("3020.BC", r)
        r = self.responder("la segunda")
        self.assertIn("50 piezas", r)
        self.assertIn("100 piezas", r)

    def test_editar_eliminar(self):
        self.responder("cotizar 100 1481.NB")
        self.responder("AGREGAR 50 3020.NG")
        self.responder("CAMBIAR 1 75")
        r = self.responder("QUITAR 2")
        self.assertIn("75 piezas", r)
        self.assertNotIn("3020.NG", r)

    def test_cancelar_no_guardar(self):
        self.responder("cotizar 100 1481.NB")
        self.responder("LISTO")
        self.responder("Monterrey")
        self.responder("CANCELAR")
        self.assertEqual(self.guardados, [])
        self.assertFalse(carrito_flujo.SESIONES)

    def test_sin_base_no_hay_folio(self):
        self.responder("cotizar 100 1481.NB")
        self.responder("LISTO")
        self.responder("Monterrey")
        self.db_listo = False
        self.assertIn("No se creó ningún folio", self.responder("CONFIRMAR"))
        self.assertEqual(self.guardados, [])


    def test_inicio_generico_pide_producto(self):
        for inicio in ("cotizar", "quiero cotizar", "cotizacion", "carrito"):
            carrito_flujo.SESIONES.clear()
            texto = self.responder(inicio)
            self.assertIn("¿Qué producto", texto)
            self.assertNotIn("No encontré", texto)
            opcion = self.responder("cajas para anillos")
            self.assertIn("1481.NB", opcion)

    def test_cualquier_cantidad_valida(self):
        for cantidad in (1, 20, 37, 125, 750, 100000):
            carrito_flujo.SESIONES.clear()
            respuesta = self.responder(f"cotizar {cantidad} 1481.NB")
            self.assertIn(f"{cantidad} piezas", respuesta)
            self.assertIn("1481.NB", respuesta)

    def test_recuperar_producto_no_encontrado_en_lote(self):
        self.responder("cotizar 100 cajas para anillos y 20 producto inexistente")
        sin_catalogo = self.responder("1")
        self.assertIn("No encontré", sin_catalogo)
        # Debe recordar las 20 piezas mientras se aclara el segundo producto.
        busqueda = self.responder("cajas para collares")
        self.assertIn("3020.NG", busqueda)
        respuesta = self.responder("1")
        self.assertIn("100 piezas", respuesta)
        self.assertIn("20 piezas", respuesta)

    def test_no_guardar_sin_confirmar(self):
        self.responder("cotizar 100 1481.NB")
        self.responder("LISTO")
        self.responder("Monterrey")
        respuesta = self.responder("OK")
        self.assertIn("CONFIRMAR", respuesta)
        self.assertEqual(self.guardados, [])


if __name__ == "__main__":
    unittest.main()
