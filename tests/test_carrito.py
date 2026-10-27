import unittest

from carrito_cotizacion import (
    agregar_linea, cambiar_cantidad, extraer_lotes,
    quitar_linea, resumen_carrito, validar_cantidad,
)


class CarritoTests(unittest.TestCase):
    def test_mensaje_dos_productos(self):
        self.assertEqual(
            extraer_lotes("Quiero cotizar 100 cajas para anillos y 50 cajas para collares"),
            [
                {"descripcion": "cajas para anillos", "cantidad": 100},
                {"descripcion": "cajas para collares", "cantidad": 50},
            ]
        )

    def test_cantidades_y_errores(self):
        self.assertEqual(validar_cantidad("100 piezas"), 100)
        self.assertEqual(validar_cantidad("50 pz"), 50)
        for error in ("0", "1000000", "dos cajas"):
            self.assertIsNone(validar_cantidad(error))

    def test_mensaje_ambiguo_sin_cantidad(self):
        self.assertEqual(extraer_lotes("quiero cajas y estuches"), [])

    def test_agregar_y_agrupar(self):
        carrito = []
        agregar_linea(carrito, {"nombre": "Caja navy", "ref": "1481.NB"}, 100)
        agregar_linea(carrito, {"nombre": "Caja navy", "ref": "1481.nb"}, 50)
        self.assertEqual(carrito[0]["cantidad"], 150)
        self.assertEqual(len(carrito), 1)

    def test_cambiar_y_eliminar(self):
        carrito = []
        agregar_linea(carrito, {"nombre": "Navy", "ref": "1481.NB"}, 100)
        agregar_linea(carrito, {"nombre": "Rosa", "ref": "1481.PK"}, 50)
        cambiar_cantidad(carrito, 2, 75)
        quitar_linea(carrito, 1)
        self.assertEqual(carrito[0]["ref"], "1481.PK")
        self.assertIn("75 piezas", resumen_carrito(carrito))

    def test_maximo_20_renglones(self):
        carrito = []
        for n in range(20):
            agregar_linea(carrito, {"nombre": f"Modelo {n}", "ref": f"REF{n}"}, 1)
        with self.assertRaises(ValueError):
            agregar_linea(carrito, {"nombre": "Extra", "ref": "REF21"}, 1)

    def test_cantidad_acumulada_limitada(self):
        carrito = []
        agregar_linea(carrito, {"nombre": "Navy", "ref": "1481.NB"}, 100000)
        with self.assertRaises(ValueError):
            agregar_linea(carrito, {"nombre": "Navy", "ref": "1481.NB"}, 1)


    def test_cantidades_variables_y_sin_cotizar(self):
        ejemplos = [
            ("quiero 100 cajas para anillos y 20 cajas para collares", [100, 20]),
            ("necesito 37 anillos y 75 collares", [37, 75]),
            ("Quiero cotizar 250 cajas azules, 80 cajas rosas; 15 cajas negras", [250, 80, 15]),
            ("100 cajas para anillos y 50 cajas para collares", [100, 50]),
        ]
        for entrada, cantidades in ejemplos:
            with self.subTest(entrada=entrada):
                self.assertEqual([p["cantidad"] for p in extraer_lotes(entrada)], cantidades)

    def test_no_adivina_cantidades_invalidas(self):
        for texto in [
            "quiero 0 cajas para anillos",
            "quiero 1000000 cajas para anillos",
            "quiero 100 cajas para anillos y veinte para collares",
        ]:
            with self.subTest(texto=texto):
                self.assertEqual(extraer_lotes(texto), [])


if __name__ == "__main__":
    unittest.main()
