"""Información operativa de Carnevali confirmada por la dirección.

Origen: respuestas facilitadas por la propietaria y fotografía de sucursales;
Matriz: número 644 confirmado posteriormente. Los teléfonos de sucursales
son teléfonos publicados; NO se presumen números de WhatsApp de ventas.
No fijar precios ni prometer existencias, descuentos o fletes.
"""
import re
import unicodedata

WEB = "https://carnevaliestuches.com"

SUCURSALES = {
    "valle": {
        "nombre": "Valle",
        "direccion": "Mississippi 415-2, entre Río Rosas y Gómez Morín, Plaza Santorini, San Pedro Garza García, N.L.",
        "telefono": "81 2710 7618 / 81 2710 7630",
        "semana": "lunes a viernes de 10:00 a 18:30",
        "sabado": "sábado de 10:00 a 13:30",
    },
    "matriz": {
        "nombre": "Matriz (Centro)",
        "direccion": "Juan Méndez 644 Norte, Centro de Monterrey, N.L.",
        "telefono": "81 8374 0873 / 81 8374 4167",
        "semana": "lunes a viernes de 10:00 a 18:30",
        "sabado": "sábado de 10:00 a 13:00",
    },
    "plaza": {
        "nombre": "Plaza México",
        "direccion": "Emilio Carranza 832, locales 11–12, Centro de Monterrey, N.L.",
        "telefono": "81 8343 0265 / 81 1492 9332",
        "semana": "lunes a viernes de 10:00 a 19:00",
        "sabado": "sábado de 10:30 a 18:00",
    },
}

CONTACTO_VENTAS = (
    "Para asesoría, cotizaciones y casos especiales, contacta al equipo "
    f"de ventas desde la página oficial: {WEB}. "
    "Teléfonos de Matriz: 81 8374 0873 y 81 8374 4167; "
    "puedes pedir los de otras sucursales. Estos son teléfonos publicados, "
    "no números de WhatsApp verificados. "
    "La transferencia automática a un vendedor todavía no está habilitada."
)


def normalizar(texto):
    s = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def _sucursal(texto):
    if any(t in texto for t in ("plaza mexico", "plaza méxico", "plaza méjico")):
        return "plaza"
    if re.search(r"\b(matriz|juan mendez|mendez)\b", texto):
        return "matriz"
    if re.search(r"\b(valle|santorini|mississippi|san pedro)\b", texto):
        return "valle"
    return None


def _detalle_sucursal(key):
    info = SUCURSALES[key]
    return (
        f"📍 Carnevali {info['nombre']}\n"
        f"Dirección: {info['direccion']}\n"
        f"Teléfonos: {info['telefono']}\n"
        f"Horario: {info['semana']}; {info['sabado']}."
    )


def _listado_sucursales():
    return "\n\n".join(_detalle_sucursal(key) for key in ("valle", "matriz", "plaza"))


def responder_pregunta_frecuente(texto):
    """Responde únicamente hechos autorizados; None deja seguir al catálogo."""
    n = normalizar(texto)
    if not n or len(n) > 500:
        return None
    palabras = set(re.findall(r"[a-z0-9]+", n))

    def tiene(*palabras_objetivo):
        return bool(palabras.intersection(palabras_objetivo))

    # Estas intenciones deben ganar prioridad sobre «sucursal» o «dónde».
    # De lo contrario «recoger en sucursal» daría solamente direcciones.
    if tiene("asesor", "asesora", "humano", "humana", "vendedor", "vendedora", "ventas") or any(
        s in n for s in ("hablar con alguien", "hablar con una persona", "atencion humana")
    ):
        return CONTACTO_VENTAS

    if tiene("recoger", "recoleccion", "recogida"):
        return (
            "Sí, puedes recoger tu compra en una sucursal. "
            "La disponibilidad y la sucursal de entrega deben "
            "coordinarse con ventas. Escribe UBICACIONES para conocerlas."
        )

    # «¿Dónde va mi pedido?» es seguimiento, no la ubicación de una tienda.
    if (tiene("pedido", "pedidos", "orden", "ordenes", "paquete") and
            tiene("donde", "estado", "estatus", "status", "llego", "llega", "salio")):
        return (
            "Para rastrear un pedido, ventas comparte la guía de paquetería "
            "cuando el envío se realiza. Este bot aún "
            "no consulta estados de pedidos en tiempo real. " + CONTACTO_VENTAS
        )

    sucursal = _sucursal(n)
    consulta_sucursal = tiene(
        "sucursal", "sucursales", "direccion", "direcciones", "ubicacion",
        "ubicaciones", "ubican", "ubicados", "horario", "horarios",
        "abren", "cierran", "abierto", "abierta", "sabado", "domingo",
        "telefono", "telefonos", "locales", "plaza"
    ) or "a que hora" in n or "numero de la" in n or bool(
        re.search(r"\bdonde\s+(?:estan|quedan|se\s+encuentran)\b", n)
    )
    if consulta_sucursal or n in {"valle", "matriz", "plaza mexico"} or (
        sucursal and re.search(r"\b(donde|esta|queda|encuentro|visitar)\b", n)
    ):
        if sucursal:
            return _detalle_sucursal(sucursal)
        if re.search(r"\bcentro\b", n):
            return ("Tenemos dos sucursales en el Centro de Monterrey:\n\n"
                    + _detalle_sucursal("matriz") + "\n\n" + _detalle_sucursal("plaza"))
        return "Estas son nuestras tres sucursales en Monterrey:\n\n" + _listado_sucursales()

    if tiene("reclamo", "reclamos", "dano", "danado", "danada", "danados",
             "incompleto", "incompleta", "equivocado", "equivocada", "devolucion",
             "devoluciones", "defectuoso", "defectuosa", "cambio", "cambios"):
        return (
            "Si recibiste mercancía dañada o un producto equivocado, "
            "Carnevali revisa el caso y gestiona su reposición o cambio. "
            "Las devoluciones se aceptan por mercancía dañada; los cambios "
            "de diseño deben solicitarse antes de facturar. "
            "Para revisar el caso, contacta a ventas. " + CONTACTO_VENTAS
        )

    if tiene("cancelar", "cancelacion", "cancelaciones") and tiene(
        "pedido", "pedidos", "compra", "compras", "anticipo"
    ):
        return (
            "Las cancelaciones sin anticipo pueden gestionarse con ventas. "
            "Si ya pagaste un anticipo, necesitamos revisión de un vendedor "
            "antes de confirmar cualquier cancelación. " + CONTACTO_VENTAS
        )

    if tiene("factura", "facturar", "facturacion", "cfdi", "fiscal", "rfc"):
        return (
            "Para emitir factura necesitamos tus datos de la Constancia "
            "de Situación Fiscal. Compártelos únicamente por el canal "
            "autorizado que indique ventas, no por este chat automático. "
            + CONTACTO_VENTAS
        )

    if tiene("guia", "rastreo", "rastrear", "seguimiento", "estatus", "status") or (
        tiene("pedido", "orden") and tiene("llego", "llega", "llegara", "llegar", "recibir", "salio", "estado", "donde")
    ):
        return (
            "Cuando se envía tu pedido, el equipo comparte la guía de "
            "paquetería para que puedas consultar su seguimiento. "
            "Este bot aún no consulta estados de pedidos en tiempo real. "
            + CONTACTO_VENTAS
        )

    if tiene("personalizar", "personalizado", "personalizada", "personalizados",
             "personalizacion", "serigrafia", "hotstamping", "hot", "stamping",
             "impresion", "imprimir", "logo", "logotipo"):
        return (
            "Personalizamos estuches mediante serigrafía o hot stamping, "
            "según el material. La cantidad mínima es de 100 piezas por "
            "tamaño y necesitamos el logotipo vectorizado. La producción "
            "suele tomar aproximadamente 2 a 3 semanas según temporada. "
            "Los precios de impresión, la técnica y el anticipo los "
            "confirma exclusivamente una vendedora. " + CONTACTO_VENTAS
        )

    if tiene("mayoreo", "mayorista", "descuento", "descuentos", "volumen",
             "menudeo", "minorista") or "5%" in n:
        return (
            "Vendemos desde una pieza a precio de menudeo y manejamos "
            "mayoreo según el volumen. En compras grandes puede evaluarse "
            "un descuento de hasta 5%, pero no es automático: ventas "
            "debe autorizar precios, cantidades y descuentos. "
            f"Consulta los precios publicados en {WEB}."
        )

    if tiene("minimo", "minima", "minimos", "minimas") and tiene(
        "compra", "compras", "pedido", "pedidos", "online", "linea", "comprar"
    ):
        return (
            "El mínimo de compra en la tienda en línea es de $800 MXN. "
            "Para compras en sucursal o condiciones de mayoreo, "
            "consulta con ventas."
        )

    if tiene("cotizacion", "cotizaciones", "cotizar") and tiene(
        "vigencia", "dura", "duran", "validez", "valida", "validas", "semana"
    ):
        return (
            "Una cotización emitida y aprobada por ventas tiene una "
            "vigencia de una semana. El carrito automático es solo una "
            "solicitud; no fija precios ni constituye un pedido."
        )

    if tiene("paypal", "transferencia", "transferencias", "tarjeta", "tarjetas",
             "efectivo", "cheque", "credito", "debito") or (
        tiene("pago", "pagos", "pagar") and not tiene("anticipo")
    ):
        return (
            "Aceptamos efectivo, transferencia, PayPal, cheque y tarjetas "
            "de crédito o débito. Un vendedor confirma el importe y "
            "las instrucciones de pago antes de completar la compra. "
            "Nunca envíes datos de tarjeta ni comprobantes sensibles aquí."
        )

    if tiene("anticipo") and not tiene("cancelar", "cancelacion"):
        return (
            "Para trabajos con impresión de logotipo se requiere anticipo. "
            "El monto y las condiciones los confirma ventas antes de "
            "iniciar la producción."
        )

    if tiene("existencia", "existencias", "inventario", "stock", "disponible",
             "disponibilidad", "agotado", "agotada"):
        return (
            "El inventario de Dolibarr puede mostrar existencias, pero "
            "no siempre está actualizado en tiempo real. Ventas debe "
            "confirmar disponibilidad antes del pago. Si no hay "
            "suficientes piezas, podemos consultar un pedido especial "
            "y su plazo de entrega."
        )

    if tiene("tiempo", "tarda", "tardan", "tardaria", "dias", "paqueteria",
             "paqueterias", "flete", "fletes", "envio", "envios",
             "entrega", "entregas", "enviar", "envian", "recoger",
             "recoleccion", "recogida", "foraneo", "internacional"):
        if tiene("recoger", "recoleccion", "recogida"):
            return (
                "Sí, puedes recoger tu compra en sucursal. "
                "La disponibilidad y la sucursal de entrega deben "
                "coordinarse con ventas. Escribe UBICACIONES para verlas."
            )
        if tiene("flete", "fletes", "costo", "cuesta", "precio"):
            return (
                "El costo del envío se cotiza según peso y volumen, "
                "además del destino. Ventas debe confirmar el flete, "
                "especialmente para envíos foráneos. " + CONTACTO_VENTAS
            )
        return (
            "📦 Hacemos envíos a todo México y podemos consultar envíos "
            "internacionales (con flete adicional). El tiempo habitual "
            "de entrega es de 3 a 6 días hábiles, sujeto a existencias, "
            "destino y producto. Manejamos distintas paqueterías según "
            "la preferencia del cliente. Ventas confirma el costo "
            "según peso y volumen; también puedes recoger en sucursal."
        )

    if tiene("precio", "precios", "costos", "costo", "cuesta", "cuestan"):
        return (
            f"Puedes consultar los precios publicados en el catálogo en {WEB}. "
            "Las cotizaciones definitivas, descuentos, impresión y "
            "fletes los revisa una vendedora. "
            "Si deseas solicitar una cotización, escribe COTIZAR."
        )

    if tiene("pagina", "web", "sitio", "catalogo", "catalogos", "shopify", "online"):
        return (
            f"Nuestro catálogo y tienda en línea están en {WEB}. "
            "También puedes escribir PRODUCTOS o solicitar una ficha "
            "exacta con FICHA y la referencia, por ejemplo FICHA 3801.RD."
        )

    if tiene("productos", "venden", "manejan", "especializan"):
        return (
            "Carnevali se especializa en suministros para el gremio joyero: "
            "estuches, cajas y exhibidores. Puedes buscar modelos por "
            "nombre o referencia en Dolibarr; los precios especiales "
            "y existencias finales se confirman con ventas."
        )

    return None


def es_consulta_independiente(texto):
    """Permitir resolver dudas comerciales mientras se mantiene un carrito.

    Una pregunta sobre el listado («¿qué productos son?») debe seguir
    llegando al selector de modelos, no a una FAQ genérica.
    """
    n = normalizar(texto).lstrip("¿¡!? ").rstrip("¿¡!? .")
    if n in {"que productos son", "que opciones son", "esto que es",
             "cual quieres", "cuales son", "que modelo es"}:
        return False
    comandos = {
        "horario", "horarios", "ubicacion", "ubicaciones",
        "direccion", "direcciones", "telefonos", "telefono",
        "envios", "envio", "formas de pago", "metodos de pago",
        "mayoreo", "devoluciones", "facturacion",
    }
    if n in comandos:
        return True
    pregunta = re.match(
        r"^(?:que|cual|cuales|como|cuando|donde|a que hora|"
        r"tienen|manejan|hacen|aceptan|puedo|podria|cuanto|cuantos|"
        r"cuantas|quiero saber|necesito un asesor|"
        r"quiero hablar con|tienes|cuentan con)\b", n
    )
    tema = re.search(
        r"\b(?:horarios?|sucursales?|direcciones?|ubicaciones?|"
        r"telefonos?|cierra|cierran|abre|abren|valle|matriz|plaza|mayoreo|menudeo|descuentos?|precios?|"
        r"costos?|cuesta|envios?|entregas?|fletes?|"
        r"paqueterias?|personalizacion|serigrafia|"
        r"hotstamping|logo|impresion|pagos?|pagar|paypal|"
        r"facturas?|facturacion|devoluciones?|cambios?|"
        r"garantia|garantias|rastreo|guias?|seguimiento|"
        r"existencias?|inventario|stock|domingos?|sabados?|"
        r"catalogo)\b", n
    )
    return bool(pregunta and tema)
