
from flask import Flask, request
import requests
import os
import re
import unicodedata

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

DOLIBARR_URL = "https://carnevali.dolibarrmnet.com/api/index.php"
DOLIBARR_API_KEY = os.getenv("DOLIBARR_API_KEY")


PALABRAS_COMUNES = {
    "hola", "buenas", "buenos", "dias", "tardes", "noches",
    "tienen", "tiene", "tendran", "tengo", "hay", "quiero",
    "quisiera", "necesito", "busco", "buscar", "buscando",
    "mostrar", "muestrame", "pueden", "puedes", "manejan",
    "venden", "me", "por", "favor", "para", "con", "sin",
    "una", "uno", "unos", "unas", "el", "la", "los", "las",
    "de", "del", "en", "un", "y", "que", "cual",
    "cuanto", "cuesta", "precio", "precios",
    "producto", "productos", "articulo", "articulos",
    "disponible", "disponibilidad", "algun", "alguna",
    "es", "esto", "este", "esta", "saber", "ustedes"
}


def normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def obtener_terminos(texto):
    palabras = re.findall(r"[a-z0-9]+", normalizar(texto))
    resultado = []

    for palabra in palabras:
        if palabra in PALABRAS_COMUNES or len(palabra) < 3:
            continue

        if palabra == "relojes":
            palabra = "reloj"
        elif palabra.endswith("s") and len(palabra) > 4:
            palabra = palabra[:-1]

        if palabra not in resultado:
            resultado.append(palabra)

    return resultado[:4]


def buscar_productos(terminos=None, limite=10):
    if not DOLIBARR_API_KEY:
        print("ERROR: Falta DOLIBARR_API_KEY")
        return None

    parametros = {"limit": limite}

    if terminos:
        # Terminos de letras/numeros solamente: no insertamos texto
        # arbitrario del cliente en el filtro de Dolibarr.
        seguros = [
            re.sub(r"[^a-z0-9]", "", t)[:32]
            for t in terminos
        ]
        seguros = [t for t in seguros if t]

        if not seguros:
            return []

        if len(seguros) == 1:
            t = seguros[0]
            parametros["sqlfilters"] = (
                f"((t.label:like:'%{t}%') or (t.ref:like:'%{t}%'))"
            )
        else:
            condiciones = [
                f"(t.label:like:'%{t}%')" for t in seguros
            ]
            parametros["sqlfilters"] = (
                "(" + " and ".join(condiciones) + ")"
            )

    try:
        respuesta = requests.get(
            f"{DOLIBARR_URL}/products",
            headers={"DOLAPIKEY": DOLIBARR_API_KEY},
            params=parametros,
            timeout=8
        )
        print("Dolibarr status:", respuesta.status_code)

        if respuesta.status_code != 200:
            print("Dolibarr error:", respuesta.text[:250])
            return None

        productos = respuesta.json()
        if not isinstance(productos, list):
            print("Respuesta inesperada de Dolibarr")
            return None

        print("Productos recibidos:", len(productos))
        return productos

    except (requests.RequestException, ValueError) as error:
        print("Error consultando Dolibarr:", type(error).__name__)
        return None


def responder_pregunta_frecuente(texto):
    """Respuestas simples; no confirma precios ni existencias."""
    palabras = set(re.findall(r"[a-z0-9]+", normalizar(texto)))

    def menciona(*opciones):
        return bool(palabras.intersection(opciones))

    # Si piden una persona, no prometemos transferencias automaticas.
    if menciona("asesor", "asesora", "humano", "humana", "vendedor", "vendedora"):
        return (
            "Con gusto te orientamos. Si necesitas atencion de ventas, "
            "puedes consultar los canales de contacto en "
            "https://carnevaliestuches.com. "
            "Este bot aun no transfiere conversaciones automaticamente."
        )

    if menciona(
        "horario", "horarios", "abren", "cierran", "abierto",
        "abierta", "sabado", "domingos", "domingo"
    ):
        return (
            "Nuestro horario habitual es de lunes a viernes de "
            "10:00 a.m. a 6:30 p.m., y sabados de 10:00 a.m. "
            "a 2:00 p.m. Te recomendamos confirmar el horario "
            "de la sucursal que visitaras."
        )

    if menciona(
        "sucursal", "sucursales", "ubicacion", "ubicaciones",
        "direccion", "direcciones", "ubicados", "donde",
        "tiendas", "locales"
    ):
        return (
            "Contamos con puntos de atencion en Centro de Monterrey, "
            "zona Del Valle en San Pedro y Plaza Mexico. "
            "Para confirmar la direccion de la sucursal que "
            "te interesa, consulta https://carnevaliestuches.com."
        )

    if menciona(
        "envio", "envios", "enviar", "envian", "paqueteria",
        "entrega", "entregas", "mandan", "foraneo", "foraneos"
    ):
        # No repetir la pregunta por la ciudad si ya la mencionaron.
        destinos = {
            "guadalajara": "Guadalajara",
            "monterrey": "Monterrey",
            "puebla": "Puebla",
            "queretaro": "Querétaro",
            "saltillo": "Saltillo",
            "merida": "Mérida",
            "tijuana": "Tijuana",
            "cancun": "Cancún",
            "chihuahua": "Chihuahua",
            "cdmx": "Ciudad de México",
            "ciudad de mexico": "Ciudad de México",
            "mexico df": "Ciudad de México",
        }
        texto_normalizado = normalizar(texto)
        destino = next((
            nombre for palabra, nombre in destinos.items()
            if re.search(r"\b" + re.escape(palabra) + r"\b",
                         texto_normalizado)
        ), None)

        if destino:
            return (
                f"¡Claro! 📦 Anotado: envío a {destino}. "
                "Hacemos envíos nacionales; el costo y tiempo se "
                "confirman según el pedido. "
                "¿Qué producto y cuántas piezas necesitas?"
            )

        return (
            "Si, realizamos envios nacionales en Mexico. 📦 "
            "El costo depende del destino y del volumen del pedido. "
            "El tiempo de entrega se confirma segun el pedido. "
            "¿A que ciudad te gustaria que enviemos?"
        )

    if menciona(
        "personalizar", "personalizado", "personalizada",
        "personalizados", "personalizadas", "personalizacion",
        "logo", "logotipo", "grabado", "impresion"
    ):
        return (
            "Podemos revisar opciones de personalizacion de "
            "estuches con tu logotipo. ✨ "
            "Dinos que tipo de estuche necesitas y cuantas piezas "
            "buscas. Disponibilidad, costo y detalles de "
            "personalizacion deben confirmarse con ventas."
        )

    if menciona(
        "cotizacion", "cotizaciones", "cotizar", "cotizame",
        "presupuesto", "precio", "precios", "cuesta", "cuestan",
        "costo", "costos", "mayoreo", "mayorista"
    ):
        return (
            "Con gusto te orientamos para cotizar. "
            "Indicanos el producto o codigo de referencia y "
            "cuantas piezas necesitas. "
            "Por ahora el bot no confirma precios ni envia "
            "cotizaciones automaticamente. Para solicitar "
            "atencion de ventas, consulta https://carnevaliestuches.com."
        )

    if menciona(
        "pedido", "pedidos", "orden", "ordenes",
        "seguimiento", "rastreo", "rastrear", "pago",
        "pagos", "factura", "facturacion"
    ):
        return (
            "Para consultar el estado de tu pedido, pago o factura "
            "necesitas atencion del equipo de ventas. "
            "Este bot todavia no consulta pedidos de Shopify. "
            "Puedes encontrar canales de contacto en "
            "https://carnevaliestuches.com."
        )

    if menciona("comprar", "compra", "compro", "compras", "tienda", "online"):
        return (
            "Puedes explorar nuestra tienda en linea en "
            "https://carnevaliestuches.com. "
            "Si buscas algo especifico, escribeme el nombre "
            "o referencia y te ayudo a encontrarlo en el catalogo."
        )

    return None


def preparar_respuesta(texto):
    texto_limpio = normalizar(texto.strip())

    if texto_limpio in {"hola", "buenas", "buenos dias", "buenas tardes"}:
        return (
            "¡Hola! 👋 Bienvenido a Carnevali Estuches. "
            "Puedes escribir PRODUCTOS o preguntar por lo que "
            "necesitas, por ejemplo: cajas para anillos."
        )

    frecuente = responder_pregunta_frecuente(texto)
    if frecuente is not None:
        return frecuente

    if texto_limpio in {"productos", "producto", "catalogo"}:
        productos = buscar_productos(limite=5)
        titulo = "Algunos productos de Carnevali Estuches:"
    else:
        terminos = obtener_terminos(texto)

        if not terminos:
            return (
                "Dime que producto buscas. Por ejemplo: "
                "'cajas para anillos', 'liston rojo' "
                "o una referencia como 0038001N."
            )

        # Busca por nombre (varias palabras) o referencia.
        productos = buscar_productos(terminos, limite=30)

        # Si la descripcion completa no coincide, prueba
        # con el ultimo termino importante.
        if productos == [] and len(terminos) > 1:
            productos = buscar_productos([terminos[-1]], limite=30)

        titulo = "Encontre estos productos relacionados:"

    if productos is None:
        return (
            "Por el momento no puedo consultar el catalogo. "
            "Intenta de nuevo mas tarde."
        )

    if not productos:
        return (
            "No encontre productos con esa descripcion. "
            "Prueba con otra palabra o un codigo de referencia."
        )

    respuesta = titulo + "\n\n"

    for producto in productos[:5]:
        nombre = producto.get("label") or producto.get("ref") or "Sin nombre"
        referencia = producto.get("ref") or ""
        respuesta += f"• {nombre}"
        if referencia:
            respuesta += f" (Ref: {referencia})"
        respuesta += "\n"

    respuesta += (
        "\nLos productos vienen de nuestro catalogo. "
        "Precio y existencias por confirmar."
    )
    return respuesta


@app.route("/", methods=["GET"])
def home():
    return "Bot de joyeria funcionando", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():

    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200

        return "Verification failed", 403

    data = request.get_json(silent=True) or {}

    try:
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])

        if not messages:
            return "EVENT_RECEIVED", 200

        message = messages[0]

        if message.get("type") == "text":
            sender = message["from"]
            texto = message["text"]["body"]

            respuesta_bot = preparar_respuesta(texto)

            url = (
                f"https://graph.facebook.com/v23.0/"
                f"{PHONE_NUMBER_ID}/messages"
            )

            headers = {
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json"
            }

            # Meta acepto el formato 52 para este numero mexicano.
            # Intentamos 52 primero cuando el webhook llega como 521.
            es_521 = bool(re.fullmatch(r"521\d{10}", sender))
            destinatario = "52" + sender[3:] if es_521 else sender

            payload = {
                "messaging_product": "whatsapp",
                "to": destinatario,
                "type": "text",
                "text": {
                    "body": respuesta_bot
                }
            }

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=15
            )

            print("WhatsApp status:", response.status_code)

            if response.status_code >= 400:
                try:
                    detalle = response.json().get("error", {})
                    print("WhatsApp error code:", detalle.get("code"))
                    print("WhatsApp error subcode:", detalle.get("error_subcode"))
                    print("WhatsApp error message:", detalle.get("message"))

                    # Si un destinatario mexicano necesita 521,
                    # se conserva un reintento con el formato original.
                    if detalle.get("code") == 131030 and es_521:
                        payload["to"] = sender
                        print("Probando formato mexicano original 521")
                        reintento = requests.post(
                            url,
                            headers=headers,
                            json=payload,
                            timeout=15
                        )
                        print("WhatsApp MX retry status:", reintento.status_code)
                        if reintento.status_code >= 400:
                            try:
                                error_mx = reintento.json().get("error", {})
                                print("WhatsApp MX retry error code:",
                                      error_mx.get("code"))
                                print("WhatsApp MX retry error message:",
                                      error_mx.get("message"))
                            except ValueError:
                                print("WhatsApp MX retry: respuesta no JSON")
                except ValueError:
                    print("WhatsApp error: respuesta no es JSON")

    except Exception as e:
        print("Error webhook:", type(e).__name__, str(e))

    return "EVENT_RECEIVED", 200
