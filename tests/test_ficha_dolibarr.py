"""Ficha real por referencia, sin llamadas externas ni datos inventados."""
import unittest
from unittest.mock import Mock

from ficha_dolibarr import consultar_ficha


class FichaTests(unittest.TestCase):
    def setUp(self):
        self.url = "https://example.com/api/index.php"
        self.ref = "3801.RD"

    def get(self, status=200, data=None):
        http = Mock()
        resp = Mock(status_code=status)
        resp.json.return_value = data
        http.get.return_value = resp
        return http

    def test_ficha_descripcion_y_stock_solo_orientativo(self):
        http = self.get(200, {
            "ref": "3801.RD",
            "label": "Estuche anillo rojo",
            "description": "<p>Cartón con interior de terciopelo</p>",
            "stock_reel": "27",
            "note_public": "Color rojo",
            "price": 123,
        })
        r = consultar_ficha(self.ref, self.url, "clave_falsa", http)
        self.assertIn("Estuche anillo rojo", r)
        self.assertIn("terciopelo", r)
        self.assertIn("Existencias registradas: 27 (por confirmar", r)
        self.assertIn("Color rojo", r)
        self.assertNotIn("123", r)
        self.assertIn("Precios especiales", r)
        self.assertEqual(http.get.call_args.args[0], self.url + "/products/ref/3801.RD")

    def test_no_acepta_ref_diferente(self):
        http = self.get(200, {"ref": "3801.BK", "label": "Estuche negro"})
        r = consultar_ficha(self.ref, self.url, "clave_falsa", http)
        self.assertIn("referencia exacta", r)
        self.assertNotIn("Estuche negro", r)

    def test_ficha_sin_medidas_no_las_inventa(self):
        http = self.get(200, {"ref": self.ref, "label": "Modelo", "stock_reel": None})
        r = consultar_ficha(self.ref, self.url, "clave_falsa", http)
        self.assertNotIn("cm", r)
        self.assertNotIn("Disponibles:", r)
        self.assertIn("consulta al equipo de ventas", r)

    def test_falla_404_y_sin_clave_no_inventa_producto(self):
        http = self.get(404)
        r = consultar_ficha(self.ref, self.url, "clave_falsa", http)
        self.assertIn("No encontré", r)
        self.assertNotIn("carrito", r)
        http.get.reset_mock()
        r = consultar_ficha(self.ref, self.url, None, http)
        self.assertIn("No está configurada", r)
        http.get.assert_not_called()

    def test_referencia_maliciosa_no_consulta_api(self):
        http = Mock()
        r = consultar_ficha("../../index.php", self.url, "clave_falsa", http)
        self.assertIn("referencia válida", r)
        http.get.assert_not_called()

if __name__ == "__main__":
    unittest.main()
