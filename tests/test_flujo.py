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


    def test_otra_no_pierde_98_anillos_ni_15_pulseras(self):
        """Reproduce el error reportado con capturas del WhatsApp real."""
        catalogo = [
            {"label": "ESTUCHE ANILLO MONACO AZUL", "ref": "1821"},
            {"label": "ESTUCHE ANILLO CARTE ROJO", "ref": "3801.RD"},
            {"label": "ESTUCHE ANILLO LUZ LED ROJO", "ref": "3541.RD"},
            {"label": "ESTUCHE PULSERA NEGRA", "ref": "PUL-1"},
            {"label": "ESTUCHE PULSERA ROJA", "ref": "PUL-2"},
        ]

        def buscar_prueba(terminos, limite=60):
            return [
                p for p in catalogo
                if all(t in (p["label"] + " " + p["ref"]).lower() for t in terminos)
            ][:limite]

        def responder(texto):
            return manejar_carrito(
                "5218123456789", texto, buscar_prueba,
                carrito_flujo._terminos, self.guardar, lambda: self.db_listo
            )

        responder("cotizar")
        primera = responder("Quiero 98 estuches para anillos y 15 estuches para pulseras")
        self.assertIn("1821", primera)
        alternativa = responder("Otra")
        self.assertIn("98 piezas", alternativa)
        opciones_rojas = responder("Estuche para anillo rojo")
        self.assertIn("3801.RD", opciones_rojas)
        siguiente = responder("3801.RD")
        self.assertIn("98 piezas", siguiente)
        self.assertIn("PUL", siguiente)
        estado = carrito_flujo.SESIONES["5218123456789"]
        self.assertEqual(estado["items"][0]["cantidad"], 98)
        self.assertEqual(estado["cantidad_sugerida"], 15)
        fin = responder("PUL-1")
        self.assertIn("15 piezas", fin)
        self.assertIn("98 piezas", fin)
        self.assertEqual(len(estado["items"]), 2)
        self.assertEqual(sum(p["cantidad"] for p in estado["items"]), 113)

    def test_reconoce_te_faltaron_15_de_pulsera(self):
        catalogo = [
            {"label": "ESTUCHE PARA ANILLO ROJO", "ref": "3801.RD"},
            {"label": "ESTUCHE PULSERA NEGRA", "ref": "PUL-1"},
            {"label": "ESTUCHE PULSERA ROJA", "ref": "PUL-2"},
        ]

        def buscar_prueba(terminos, limite=60):
            return [
                p for p in catalogo
                if all(t in (p["label"] + " " + p["ref"]).lower() for t in terminos)
            ][:limite]

        def responder(texto):
            return manejar_carrito(
                "5218123456789", texto, buscar_prueba,
                carrito_flujo._terminos, self.guardar, lambda: self.db_listo
            )

        responder("COTIZAR")
        responder("98 3801.RD")
        correccion = responder("Te faltaron las 15 de pulsera")
        self.assertIn("15 piezas", correccion)
        self.assertIn("PUL-1", correccion)
        resumen = responder("PUL-1")
        self.assertIn("98 piezas", resumen)
        self.assertIn("15 piezas", resumen)
        self.assertEqual([p["cantidad"] for p in carrito_flujo.SESIONES["5218123456789"]["items"]], [98, 15])

    def test_correccion_antes_de_confirmar_exige_nueva_confirmacion(self):
        self.responder("COTIZAR 98 1481.NB")
        self.responder("LISTO")
        self.responder("Monterrey")
        respuesta = self.responder("Te faltaron las 15 de collar")
        self.assertIn("15 piezas", respuesta)
        self.assertIn("3020.NG", respuesta)
        self.responder("3020.NG")
        self.assertEqual(self.guardados, [])
        self.responder("LISTO")
        revisar = self.responder("Monterrey")
        self.assertIn("113 piezas", revisar)
        self.assertEqual(self.guardados, [])
        self.responder("CONFIRMAR")
        self.assertEqual([i["cantidad"] for i in self.guardados[0][0]], [98, 15])

    def test_pedido_500_50_20_y_orden_combinada(self):
        catalogo = [
            {"label": "ESTUCHE PARA PULSERA BLANCO", "ref": "4013"},
            {"label": "CARTON 6 CADENAS COLLARES VELOUR", "ref": "4812"},
            {"label": "EXHIBIDOR 12 COLLARES", "ref": "5710"},
            {"label": "ESTUCHE PARA COLLAR NEGRO", "ref": "COL-REAL"},
            {"label": "ESTUCHE PARA ANILLO AZUL", "ref": "1821"},
        ]
        def buscar_filtrado(terminos, limite=100):
            return [
                p for p in catalogo
                if all(t in (p["label"] + " " + p["ref"]).lower() for t in terminos)
            ][:limite]
        def responder(s):
            return manejar_carrito(
                "5218123456789", s, buscar_filtrado,
                carrito_flujo._terminos, self.guardar, lambda: True
            )
        responder("COTIZAR")
        opciones = responder("Quiero 500 estuches para pulseras, 50 estuches de collares y 20 estuches de anillos")
        self.assertIn("4013", opciones)
        self.assertIn("COL-REAL", opciones)
        self.assertNotIn("CARTON", opciones)
        self.assertIn("570 piezas", opciones)
        # Si solo hay un modelo coincidente por cada rubro, el sistema
        # los agrega automáticamente tras validar su referencia real.
        self.assertEqual(
            [p["cantidad"] for p in carrito_flujo.SESIONES["5218123456789"]["items"]],
            [500, 50, 20]
        )
        mostrar = responder("que productos son?")
        self.assertIn("570 piezas", mostrar)
        quita = responder("Quiero quitar el 3 y agregar otro")
        self.assertIn("¿Qué nuevo producto", quita)
        self.assertEqual(sum(x["cantidad"] for x in carrito_flujo.SESIONES["5218123456789"]["items"]), 550)
        busca = responder("Quiero 200 cajas para aretes")
        self.assertIn("No encontré", busca)
        self.assertIn("550 piezas", responder("VER"))

    def test_pedir_fotos_no_cambia_la_seleccion(self):
        self.responder("COTIZAR")
        self.responder("100 cajas para anillos")
        r = self.responder("Quiero ver fotos para elegir")
        self.assertIn("fotografías verificadas", r)
        self.assertIn("1481.NB", r)
        self.assertEqual(carrito_flujo.SESIONES["5218123456789"]["paso"], "elegir")
        self.assertEqual(carrito_flujo.SESIONES["5218123456789"]["cantidad_sugerida"], 100)

    def test_numero_en_frase_de_cantidad(self):
        self.responder("COTIZAR")
        self.responder("cajas para anillos")
        self.responder("1")
        r = self.responder("Ya me preguntaste pero 200")
        self.assertIn("200 piezas", r)

    def test_quitar_solo_pide_numero(self):
        self.responder("cotizar 100 1481.NB")
        self.responder("agregar 50 1481.PK")
        r = self.responder("Quitar")
        self.assertIn("¿Cuál número", r)
        r2 = self.responder("2")
        self.assertIn("Quité", r2)
        self.assertIn("100 piezas", r2)
        self.assertNotIn("1481.PK", r2)

    def test_busqueda_con_uso_corrige_modelo(self):
        self.responder("COTIZAR")
        self.responder("estuches para anillos")
        r = self.responder("Pero ocupo para aretes")
        self.assertIn("No encontré", r)
        # No seleccionó accidentalmente una caja para anillos.
        self.assertEqual(carrito_flujo.SESIONES["5218123456789"]["items"], [])


if __name__ == "__main__":
    unittest.main()
