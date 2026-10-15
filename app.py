
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


def preparar_respuesta(texto):
    texto_limpio = normalizar(texto.strip())

    if texto_limpio in {"hola", "buenas", "buenos dias", "buenas tardes"}:
        return (
            "¡Hola! 👋 Bienvenido a Carnevali Estuches. "
            "Puedes escribir PRODUCTOS o preguntar por lo que "
            "necesitas, por ejemplo: cajas para anillos."
        )

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

            payload = {
                "messaging_product": "whatsapp",
                "to": sender,
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

    except Exception as e:
        print("Error webhook:", type(e).__name__, str(e))

    return "EVENT_RECEIVED", 200
