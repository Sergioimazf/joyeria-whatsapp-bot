"""Pruebas de fotografías por referencia, con respuestas HTTP simuladas.

Ninguna prueba consulta Dolibarr real ni envía mensajes a WhatsApp.
"""
import unittest
from unittest.mock import Mock, patch

import app
import carrito_flujo
from fotos_dolibarr import verificar_fotos


def respuesta(status, contenido=None):
    r = Mock(status_code=status)
    r.json.return_value = contenido
    return r


class FotosDolibarrTests(unittest.TestCase):
    def setUp(self):
        self.ref = "3801.RD"
        self.url = "https://ejemplo.test/api/index.php"

    def test_listar_fotos_por_id_de_referencia_verificada(self):
        http = Mock()
        http.get.side_effect = [
            respuesta(200, {"id": "58", "ref": self.ref, "label": "ESTUCHE ANILLO ROJO"}),
            respuesta(200, [
                {"name": "frontal.jpg", "type": "file"},
                {"name": "lateral.png", "type": "file"},
                {"name": "archivo.pdf", "type": "file"},
                {"name": ".oculto.jpg", "type": "file"},
                {"name": "detalle_preview.png", "type": "file"},
            ]),
        ]
        resultado = verificar_fotos(self.ref, self.url, "token_de_prueba", http)
        self.assertIn("2 fotografía(s)", resultado)
        self.assertIn("ESTUCHE ANILLO ROJO", resultado)
        self.assertIn("Ref: 3801.RD", resultado)
        self.assertEqual(http.get.call_count, 2)
        url_producto = http.get.call_args_list[0].args[0]
        self.assertEqual(url_producto, self.url + "/products/ref/3801.RD")
        self.assertEqual(
            http.get.call_args_list[1].kwargs["params"]["id"], 58
        )
        self.assertEqual(
            http.get.call_args_list[1].kwargs["params"]["modulepart"], "product"
        )

    def test_no_aceptar_ref_diferente_de_la_ficha(self):
        http = Mock()
        http.get.return_value = respuesta(
            200, {"id": 58, "ref": "3801.BLUE", "label": "OTRO MODELO"}
        )
        r = verificar_fotos(self.ref, self.url, "token_de_prueba", http)
        self.assertIn("coincidencia exacta", r)
        self.assertEqual(http.get.call_count, 1)

    def test_no_fotografias_no_es_fallo_de_producto(self):
        http = Mock()
        http.get.side_effect = [
            respuesta(200, {"id": 58, "ref": self.ref, "label": "ESTUCHE ROJO"}),
            respuesta(200, []),
        ]
        r = verificar_fotos(self.ref, self.url, "token_de_prueba", http)
        self.assertIn("ningún archivo", r)

    def test_sin_permisos_documentos(self):
        http = Mock()
        http.get.side_effect = [
            respuesta(200, {"id": 58, "ref": self.ref, "label": "ESTUCHE ROJO"}),
            respuesta(403),
        ]
        r = verificar_fotos(self.ref, self.url, "token_de_prueba", http)
        self.assertIn("no tiene permiso", r)

    def test_404_por_id_y_por_referencia_no_asegura_ausencia_de_fotos(self):
        http = Mock()
        http.get.side_effect = [
            respuesta(200, {"id": 58, "ref": self.ref, "label": "ESTUCHE ROJO"}),
            respuesta(404),
            respuesta(404),
        ]
        r = verificar_fotos(self.ref, self.url, "token_de_prueba", http)
        self.assertIn("respondió 404", r)
        self.assertIn("NO prueba", r)
        self.assertEqual(http.get.call_count, 3)
        self.assertEqual(http.get.call_args_list[2].kwargs["params"]["ref"], self.ref)

    def test_404_por_id_reintenta_por_referencia_y_encuentra_fotos(self):
        http = Mock()
        http.get.side_effect = [
            respuesta(200, {"id": 58, "ref": self.ref, "label": "ESTUCHE ROJO"}),
            respuesta(404),
            respuesta(200, [{"name": "frontal.jpg", "type": "file"}]),
        ]
        r = verificar_fotos(self.ref, self.url, "token_de_prueba", http)
        self.assertIn("1 fotografía(s)", r)
        self.assertEqual(http.get.call_count, 3)

    def test_error_diferente_a_404_no_confunde_con_faltan_fotos(self):
        http = Mock()
        http.get.side_effect = [
            respuesta(200, {"id": 58, "ref": self.ref, "label": "ESTUCHE ROJO"}),
            respuesta(503),
        ]
        r = verificar_fotos(self.ref, self.url, "token_de_prueba", http)
        self.assertIn("503", r)
        self.assertNotIn("no devolvió fotografías", r)

    def test_referencia_no_valida_no_llama_api(self):
        http = Mock()
        r = verificar_fotos("../secreto", self.url, "token_de_prueba", http)
        self.assertIn("referencia válida", r)
        http.get.assert_not_called()

    def test_foto_disponible_solo_en_modo_pruebas(self):
        sender = "5218123456789"
        carrito_flujo.SESIONES.clear()
        app.CARRITO_TESTERS.clear()
        app.COTIZACIONES.clear()
        with patch.object(app, "CARRITO_MODO_PRUEBA", True), \
             patch.object(app, "CARRITO_MULTIPRODUCTO", True), \
             patch.object(app, "verificar_fotos", return_value="2 fotos verificadas") as funcion:
            app.preparar_respuesta("PROBAR CARRITO", sender)
            r = app.preparar_respuesta("FOTO 3801.RD", sender)
            self.assertEqual(r, "2 fotos verificadas")
            funcion.assert_called_once_with(
                "3801.RD", app.DOLIBARR_URL, app.DOLIBARR_API_KEY
            )
            app.preparar_respuesta("SALIR PRUEBA", sender)
            funcion.reset_mock()
            app.preparar_respuesta("FOTO 3801.RD", sender)
            funcion.assert_not_called()

    def test_cotizacion_se_conserva_tras_foto(self):
        sender = "5218123456789"
        carrito_flujo.SESIONES.clear()
        app.CARRITO_TESTERS.clear()
        with patch.object(app, "CARRITO_MODO_PRUEBA", True), \
             patch.object(app, "CARRITO_MULTIPRODUCTO", True), \
             patch.object(app, "verificar_fotos", return_value="Sin fotos"):
            app.preparar_respuesta("PROBAR CARRITO", sender)
            carrito_flujo.SESIONES[sender] = {
                "paso": "carrito", "items": [{"nombre": "CAJA",
                "ref": "3801.RD", "cantidad": 100}], "actualizado": 0,
            }
            estado_antes = carrito_flujo.SESIONES[sender].copy()
            app.preparar_respuesta("FOTO 3801.RD", sender)
            self.assertEqual(carrito_flujo.SESIONES[sender], estado_antes)


if __name__ == "__main__":
    unittest.main()
