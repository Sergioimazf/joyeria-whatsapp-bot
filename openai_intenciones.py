"""Clasificador opcional de preguntas comerciales usando OpenAI Responses API.

Nunca genera una respuesta libre de precios/políticas: solo una categoría
validada. La respuesta al cliente sigue saliendo de carnevali_info.py.
Activación independiente bajo control del propietario, modo "pruebas".
No guarda conversaciones ni envia identificadores de clientes.
"""
import re

import requests

CATEGORIAS = frozenset({
    "horarios", "ubicaciones", "envios", "mayoreo", "personalizacion",
    "factura", "pagos", "devoluciones", "seguimiento", "inventario",
    "asesor", "precios", "catalogo", "otra",
})

PREGUNTA_CANONICA = {
    "horarios": "¿Cuáles son los horarios?",
    "ubicaciones": "¿Cuáles son sus sucursales?",
    "envios": "¿Hacen envíos?",
    "mayoreo": "¿Tienen mayoreo?",
    "personalizacion": "¿Personalizan con logo?",
    "factura": "¿Cómo pido factura?",
    "pagos": "¿Cómo puedo pagar?",
    "devoluciones": "¿Qué hago si me llegó mercancía dañada?",
    "seguimiento": "¿Cómo rastreo el pedido?",
    "inventario": "¿Tienen existencias de productos?",
    "asesor": "Quiero hablar con una vendedora",
    "precios": "¿Dónde veo precios?",
    "catalogo": "¿Dónde está el catálogo?",
}

INSTRUCCIONES = (
    "Eres un CLASIFICADOR, no un chatbot. Clasifica la intención principal "
    "de una pregunta de un cliente sobre un negocio de estuches para joyería. "
    "Responde con EXACTAMENTE una palabra de este conjunto, sin puntuación "
    "ni explicaciones: horarios, ubicaciones, envios, mayoreo, "
    "personalizacion, factura, pagos, devoluciones, seguimiento, "
    "inventario, asesor, precios, catalogo, otra. "
    "Si el mensaje busca modelos, productos concretos, quiere cotizar, "
    "cambiar su carrito, contiene números de referencia o es ambiguo, "
    "usa 'otra'. Nunca proporciones precios, productos o datos."
)


def _sin_datos_personales(texto):
    """No se necesita enviar teléfonos, correos o códigos fiscales a IA."""
    contenido = str(texto).strip()
    # No llamar IA para textos largos, correos, teléfonos o RFC.
    if not 3 <= len(contenido) <= 300:
        return None
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", contenido):
        return None
    if re.search(r"(?<!\d)\d[\d\s\-()]{8,}\d(?!\d)", contenido):
        return None
    if re.search(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b", contenido, flags=re.I):
        return None
    return contenido


def clasificar_pregunta(texto, api_key, model="gpt-4.1-mini", http=requests):
    """Devuelve categoría permitida o None; nunca devuelve texto libre."""
    mensaje = _sin_datos_personales(texto)
    if not mensaje or not api_key:
        return None
    if not re.fullmatch(r"[a-zA-Z0-9._-]{2,80}", model):
        return None
    try:
        r = http.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "store": False,
                "instructions": INSTRUCCIONES,
                "input": [{"role": "user", "content": mensaje}],
                "max_output_tokens": 32,
            },
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        textos = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for fragmento in item.get("content", []):
                if fragmento.get("type") == "output_text":
                    textos.append(str(fragmento.get("text") or ""))
        respuesta = " ".join(textos).strip().lower()
        return respuesta if respuesta in CATEGORIAS else None
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return None
