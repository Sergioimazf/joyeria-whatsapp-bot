"""Regresiones de políticas verificadas y consulta Dolibarr sin red real."""
import unittest
from unittest.mock import Mock, patch

import app
import carrito_flujo
from carnevali_info import responder_pregunta_frecuente, es_consulta_independiente
from ficha_dolibarr import consultar_ficha


def respuesta(status, cuerpo):
    r = Mock(status_code=status)
    r.json.return_value = cuerpo
    return r


class PoliticasTests(unittest.TestCase):
    def test_ubicaciones_y_matriz_corregida(self):
        r = responder_pregunta_frecuente("¿Dónde están las sucursales?")
        self.assertIn("Juan Méndez 644 Norte", r)
        self.assertNotIn("Méndez 664", r)
        self.assertIn("Mississippi 415-2", r)
        self.assertIn("Emilio Carranza 832", r)
        self.assertIn("13:30", r)
        self.assertIn("13:00", r)
        self.assertIn("18:00", r)

    def test_horarios_especificos(self):
        r = responder_pregunta_frecuente("Horario de Plaza México")
        self.assertIn("10:30 a 18:00", r)
        self.assertIn("81 1492 9332", r)
        r2 = responder_pregunta_frecuente("Horario de Valle")
        self.assertIn("10:00 a 13:30", r2)
        self.assertNotIn("Juan Méndez", r2)

    def test_mayoreo_y_precios_no_aprobados(self):
        r = responder_pregunta_frecuente("¿Tienen precios de mayoreo?")
        self.assertIn("hasta 5%", r)
        self.assertIn("ventas", r)
        r = responder_pregunta_frecuente("¿Cuánto cuesta?")
        self.assertIn("precios publicados", r)

    def test_monto_minimo_y_personalizacion(self):
        r = responder_pregunta_frecuente("¿Cuál es el mínimo de compra online?")
        self.assertIn("$800 MXN", r)
        r = responder_pregunta_frecuente("¿Me imprimen mi logo?")
        self.assertIn("100 piezas", r)
        self.assertIn("vectorizado", r)
        self.assertIn("2 a 3 semanas", r)
        self.assertIn("vendedora", r)

    def test_envios_y_pagos(self):
        r = responder_pregunta_frecuente("¿Hacen envíos a todo México?")
        self.assertIn("todo México", r)
        self.assertIn("3 a 6 días", r)
        r = responder_pregunta_frecuente("¿Cómo calculan el flete?")
        self.assertIn("peso y volumen", r)
        r = responder_pregunta_frecuente("¿Puedo pagar con PayPal?")
        self.assertIn("PayPal", r)
        self.assertIn("vendedor", r)

    def test_facturas_y_devoluciones(self):
        r = responder_pregunta_frecuente("Quiero factura")
        self.assertIn("Constancia de Situación Fiscal", r)
        r = responder_pregunta_frecuente("Me llegó mercancía dañada")
        self.assertIn("reposici", r)
        r = responder_pregunta_frecuente("¿Qué pasa con el seguimiento de mi guía?")
        self.assertIn("no consulta estados de pedidos", r)

    def test_cotizacion_vigencia_y_stock(self):
        r = responder_pregunta_frecuente("¿Qué vigencia tienen las cotizaciones?")
        self.assertIn("una semana", r)
        r = responder_pregunta_frecuente("¿Tienen stock actualizado?")
        self.assertIn("no siempre", r)
        self.assertIn("confirmar disponibilidad", r)

    def test_atencion_humana_no_inventa_whatsapp(self):
        r = responder_pregunta_frecuente("Quiero hablar con una vendedora")
        self.assertIn("carnevaliestuches.com", r)
        self.assertIn("no está habilitada", r)

    def test_nunca_responder_orden_de_seleccion_con_faq_generica(self):
        self.assertFalse(es_consulta_independiente("¿Qué productos son?"))
        self.assertFalse(es_consulta_independiente("¿Cuántas piezas?"))
        self.assertTrue(es_consulta_independiente("¿Qué horarios manejan?"))
        self.assertTrue(es_consulta_independiente("¿Cuánto cuesta la impresión?"))

    def test_catalogo_no_desviado_por_direccion_generica(self):
        self.assertIsNone(responder_pregunta_frecuente("100 estuches para anillos"))


class FichaApiTests(unittest.TestCase):
    def test_ficha_exacta_con_descripcion_y_stock_advertido(self):
        http = Mock()
        http.get.return_value = respuesta(200, {
            "id": 58,
            "ref": "3801.RD",
            "label": "ESTUCHE ANILLO CARTE ROJO",
            "description": "<p>Rojo, interior suave</p>",
            "stock_reel": 45,
        })
        r = consultar_ficha("3801.RD", "https://test.local/api/index.php", "token_simulado", http)
        self.assertIn("ESTUCHE ANILLO CARTE ROJO", r)
        self.assertIn("Rojo, interior suave", r)
        self.assertNotIn("<p>", r)
        self.assertIn("Existencias registradas: 45", r)
        self.assertIn("por confirmar", r)
        self.assertNotIn("precio de venta: $", r.lower())
        self.assertEqual(
            http.get.call_args.args[0], "https://test.local/api/index.php/products/ref/3801.RD"
        )

    def test_no_devuelve_modelo_incorrecto(self):
        http = Mock()
        http.get.return_value = respuesta(200, {"ref": "3801.BK", "label": "NEGRO"})
        r = consultar_ficha("3801.RD", "https://test.local/api/index.php", "token_simulado", http)
        self.assertIn("referencia exacta", r)
        self.assertNotIn("NEGRO", r)

    def test_error_y_falta_permisos_no_generan_detalles_falsos(self):
        http = Mock()
        http.get.return_value = respuesta(403, {"error": "blocked"})
        r = consultar_ficha("3801.RD", "https://test.local/api/index.php", "token_simulado", http)
        self.assertIn("No pude consultar", r)
        r = consultar_ficha("3801.RD", "https://test.local/api/index.php", None, http)
        self.assertIn("No está configurada", r)

    def test_enviar_ficha_no_modifica_carrito_activo(self):
        remitente = "5218123456789"
        carrito_flujo.SESIONES.clear()
        app.COTIZACIONES.clear()
        carrito_flujo.SESIONES[remitente] = {
            "paso": "elegir", "items": [], "actualizado": 123,
            "opciones": [{"nombre": "ROJO", "ref": "3801.RD"}],
            "cantidad_sugerida": 100
        }
        with patch.object(app, "consultar_ficha", return_value="Ficha oficial") as consulta:
            r = app.preparar_respuesta("FICHA 3801.RD", remitente)
        self.assertEqual(r, "Ficha oficial")
        consulta.assert_called_once()
        self.assertEqual(carrito_flujo.SESIONES[remitente]["cantidad_sugerida"], 100)
        self.assertEqual(carrito_flujo.SESIONES[remitente]["paso"], "elegir")
        carrito_flujo.SESIONES.clear()

    def test_preguntar_horario_mientras_se_cotiza_conserva_estado(self):
        remitente = "5218123456789"
        carrito_flujo.SESIONES.clear()
        app.COTIZACIONES.clear()
        carrito_flujo.SESIONES[remitente] = {
            "paso": "elegir", "items": [], "actualizado": 123,
            "opciones": [{"nombre": "ROJO", "ref": "3801.RD"}],
            "cantidad_sugerida": 100
        }
        r = app.preparar_respuesta("¿A qué hora cierra Valle?", remitente)
        self.assertIn("Mississippi 415-2", r)
        self.assertEqual(carrito_flujo.SESIONES[remitente]["paso"], "elegir")
        carrito_flujo.SESIONES.clear()

    def test_politicas_alcanzables_desde_whatsapp(self):
        r = app.preparar_respuesta("¿Cuáles son los métodos de pago?", sender=None)
        self.assertIn("PayPal", r)
        r = app.preparar_respuesta("¿Dónde está la Matriz?", sender=None)
        self.assertIn("Juan Méndez 644", r)


if __name__ == "__main__":
    unittest.main()
