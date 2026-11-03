"""La IA solo clasifica y nunca inventa una respuesta o un precio."""
import unittest
from unittest.mock import Mock, patch

import app
from openai_intenciones import clasificar_pregunta, PREGUNTA_CANONICA


def respuesta(categoria):
    r = Mock(status_code=200)
    r.json.return_value = {
        "output": [{"type": "message", "content": [
            {"type": "output_text", "text": categoria}
        ]}]
    }
    return r


class OpenAiIntencionesTests(unittest.TestCase):
    def test_clasifica_una_sola_etiqueta_con_api_simulada(self):
        http = Mock()
        http.post.return_value = respuesta("personalizacion")
        r = clasificar_pregunta("¿Le pueden poner mi marca al estuche?", "clave_prueba", http=http)
        self.assertEqual(r, "personalizacion")
        self.assertFalse(http.post.call_args.kwargs["json"]["store"])
        self.assertEqual(
            http.post.call_args.kwargs["url"] if "url" in http.post.call_args.kwargs
            else http.post.call_args.args[0],
            "https://api.openai.com/v1/responses",
        )

    def test_no_acepta_respuesta_libre_que_pudiera_inventar_precio(self):
        http = Mock()
        http.post.return_value = respuesta("La impresión cuesta 200 pesos.")
        self.assertIsNone(clasificar_pregunta("¿Cuánto vale imprimir?", "prueba", http=http))

    def test_sin_clave_o_error_de_api_fallback_seguro(self):
        http = Mock()
        self.assertIsNone(clasificar_pregunta("¿Pueden personalizar?", None, http=http))
        http.post.assert_not_called()
        http.post.return_value = Mock(status_code=401)
        self.assertIsNone(clasificar_pregunta("¿Pueden personalizar?", "clave", http=http))

    def test_no_enviar_numero_o_correo_de_clientes_a_api(self):
        http = Mock()
        self.assertIsNone(clasificar_pregunta("Mi número es 8112345678, quiero un pedido", "clave", http=http))
        self.assertIsNone(clasificar_pregunta("Escríbeme a cliente@test.com", "clave", http=http))
        http.post.assert_not_called()

    def test_categoria_se_traduce_a_politica_controlada(self):
        self.assertEqual(PREGUNTA_CANONICA["personalizacion"], "¿Personalizan con logo?")
        self.assertNotIn("cotizar", PREGUNTA_CANONICA)

    def test_bot_usa_ia_solo_en_pruebas_y_sin_carrito(self):
        sender = "5218123456789"
        app.CARRITO_TESTERS.clear()
        app.COTIZACIONES.clear()
        with patch.object(app, "CARRITO_MODO_PRUEBA", True), \
             patch.object(app, "CARRITO_MULTIPRODUCTO", True), \
             patch.object(app, "IA_CARNEVALI_MODO", "pruebas"), \
             patch.object(app, "OPENAI_API_KEY", "clave_prueba"), \
             patch.object(app, "clasificar_pregunta", return_value="personalizacion") as clasificar, \
             patch.object(app, "buscar_productos", return_value=[]):
            app.preparar_respuesta("PROBAR CARRITO", sender)
            r = app.preparar_respuesta("¿Les puedo poner mi marca?", sender)
            self.assertIn("100 piezas", r)
            self.assertIn("vectorizado", r)
            clasificar.assert_called_once()
            app.preparar_respuesta("SALIR PRUEBA", sender)
            clasificar.reset_mock()
            app.preparar_respuesta("¿Les puedo poner mi marca?", sender)
            clasificar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
