"""Pruebas sin API ni base real de políticas de Carnevali y rutas seguras."""
import unittest
from unittest.mock import patch, Mock

import app
import carrito_flujo
from carnevali_info import responder_pregunta_frecuente as responder


class PoliticasCarnevaliTests(unittest.TestCase):
    def test_direcciones_telefonos_y_horarios_oficiales(self):
        todas = responder("¿Me das las ubicaciones y teléfonos?")
        self.assertIn("Mississippi 415-2", todas)
        self.assertIn("Juan Méndez 644 Norte", todas)
        self.assertNotIn("Méndez 664", todas)
        self.assertIn("Emilio Carranza 832", todas)
        self.assertIn("81 2710 7618", todas)
        self.assertIn("81 8374 0873", todas)
        self.assertIn("81 8343 0265", todas)
        plaza = responder("¿A qué hora cierra Plaza México el sábado?")
        self.assertIn("18:00", plaza)
        self.assertIn("10:30", plaza)
        self.assertNotIn("Juan Méndez", plaza)
        matriz = responder("horario sucursal matriz")
        self.assertIn("sábado de 10:00 a 13:00", matriz)
        centro = responder("¿Dónde están en el centro?")
        self.assertIn("Matriz", centro)
        self.assertIn("Plaza México", centro)
        self.assertNotIn("Mississippi", centro)

    def test_politicas_mayoreo_precios_y_descuentos_no_confirmados(self):
        r = responder("¿Tienen mayoreo?")
        self.assertIn("desde una pieza", r)
        self.assertIn("5%", r)
        self.assertIn("no es automático", r)
        r = responder("¿Cuánto cuesta un estuche?")
        self.assertIn("precios publicados", r)
        self.assertIn("vendedora", r)
        self.assertNotIn("$150", r)
        r = responder("¿Cuál es el mínimo de compra en línea?")
        self.assertIn("$800 MXN", r)
        r = responder("¿Cuánto dura una cotización?")
        self.assertIn("una semana", r)
        self.assertIn("aprobada por ventas", r)

    def test_envios_personalizacion_y_recoleccion(self):
        r = responder("¿Hacen envíos a todo México?")
        self.assertIn("3 a 6 días hábiles", r)
        self.assertIn("internacionales", r)
        r = responder("¿Cuánto cuesta el flete?")
        self.assertIn("peso y volumen", r)
        self.assertIn("Ventas", r)
        r = responder("¿Puedo recoger en sucursal?")
        self.assertIn("recoger", r)
        self.assertIn("coordinarse", r)
        r = responder("¿Personalizan con logo?")
        self.assertIn("100 piezas", r)
        self.assertIn("vectorizado", r)
        self.assertIn("2 a 3 semanas", r)
        self.assertIn("vendedora", r)

    def test_venta_pagos_facturas_problemas_y_seguimiento(self):
        r = responder("¿Cómo puedo pagar?")
        for nombre in ("PayPal", "transferencia", "cheque", "crédito", "débito"):
            self.assertIn(nombre, r)
        r = responder("¿Cómo pido factura?")
        self.assertIn("Constancia", r)
        self.assertNotIn("envía tu RFC aquí", r)
        r = responder("Mi producto llegó dañado, ¿qué hago?")
        self.assertIn("reposición", r)
        self.assertIn("devoluciones", r)
        r = responder("¿Dónde está mi pedido?")
        self.assertIn("rastrear", r)
        self.assertNotIn("Mississippi", r)
        r = responder("¿Tienen inventario en tiempo real?")
        self.assertIn("no siempre", r)
        self.assertIn("confirmar", r)

    def test_deriva_vendedora_sin_inventar_telefono_whatsapp(self):
        r = responder("Quiero hablar con una persona")
        self.assertIn("81 8374 0873", r)
        self.assertIn("no números de WhatsApp verificados", r)
        self.assertIn("no está habilitada", r)


class IntegracionCarnevaliTests(unittest.TestCase):
    def setUp(self):
        app.COTIZACIONES.clear()
        app.CARRITO_TESTERS.clear()
        carrito_flujo.SESIONES.clear()

    def test_ficha_consulta_referencia_exacta_no_altera_carrito(self):
        sender = "5218123456789"
        with patch.object(app, "CARRITO_MULTIPRODUCTO", True), \
             patch.object(app, "CARRITO_MODO_PRUEBA", True), \
             patch.object(app, "consultar_ficha", return_value="Ficha correcta") as ficha:
            app.preparar_respuesta("PROBAR CARRITO", sender)
            app.preparar_respuesta("COTIZAR", sender)
            estado = carrito_flujo.SESIONES[sender].copy()
            self.assertEqual(app.preparar_respuesta("FICHA 3801.RD", sender), "Ficha correcta")
            ficha.assert_called_once_with(
                "3801.RD", app.DOLIBARR_URL, app.DOLIBARR_API_KEY
            )
            self.assertEqual(carrito_flujo.SESIONES[sender], estado)

    def test_pregunta_horarios_no_consume_carrito(self):
        sender = "5218123456789"
        with patch.object(app, "CARRITO_MULTIPRODUCTO", True), \
             patch.object(app, "CARRITO_MODO_PRUEBA", True):
            app.preparar_respuesta("PROBAR CARRITO", sender)
            app.preparar_respuesta("COTIZAR", sender)
            paso = carrito_flujo.SESIONES[sender]["paso"]
            r = app.preparar_respuesta("¿Cuál es el horario de Valle?", sender)
            self.assertIn("Mississippi 415-2", r)
            self.assertEqual(carrito_flujo.SESIONES[sender]["paso"], paso)

    def test_politicas_disponibles_sin_activar_modo_pruebas(self):
        r = app.preparar_respuesta("¿Cuál es el horario de Plaza México?", "5218111111111")
        self.assertIn("10:30", r)
        r = app.preparar_respuesta("¿Tienen mayoreo?", "5218111111111")
        self.assertIn("5%", r)

    def test_no_activa_ia_sin_credenciales_ni_autorizacion(self):
        sender = "5218123456789"
        with patch.object(app, "IA_CARNEVALI_MODO", "apagado"), \
             patch.object(app, "clasificar_pregunta") as clasificar, \
             patch.object(app, "buscar_productos", return_value=[]):
            app.preparar_respuesta("¿Les puedo poner nombre de marca?", sender)
            clasificar.assert_not_called()

if __name__ == "__main__":
    unittest.main()
