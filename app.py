
from flask import Flask, request
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

DOLIBARR_URL = "https://carnevali.dolibarrmnet.com/api/index.php"
DOLIBARR_API_KEY = os.getenv("DOLIBARR_API_KEY")


def buscar_productos():
    if not DOLIBARR_API_KEY:
        print("ERROR: Falta DOLIBARR_API_KEY")
        return None

    url = f"{DOLIBARR_URL}/products"
    headers = {"DOLAPIKEY": DOLIBARR_API_KEY}

    try:
        respuesta = requests.get(
            url,
            headers=headers,
            params={"limit": 10},
            timeout=15
        )

        print("Dolibarr status:", respuesta.status_code)
        respuesta.raise_for_status()

        productos = respuesta.json()

        if not isinstance(productos, list):
            print("Dolibarr no devolvio una lista")
            return None

        print("Productos recibidos:", len(productos))
        return productos

    except Exception as e:
        print("Error consultando Dolibarr:", type(e).__name__)
        return None


def preparar_respuesta(texto):
    if texto.strip().lower() == "productos":
        productos = buscar_productos()

        if productos is None:
            return (
                "Por el momento no podemos consultar "
                "nuestro catalogo. Intenta mas tarde."
            )

        if not productos:
            return "No se encontraron productos en la consulta."

        mensaje = "Estos son algunos productos de Carnevali Estuches:\n\n"

        for producto in productos[:5]:
            nombre = producto.get("label") or producto.get("ref") or "Sin nombre"
            referencia = producto.get("ref", "")

            mensaje += f"- {nombre}"
            if referencia:
                mensaje += f" (Ref: {referencia})"
            mensaje += "\n"

        mensaje += "\nPuedes preguntarnos por un producto en particular."
        return mensaje

    return (
        "Hola 👋 Gracias por escribir a Carnevali Estuches. "
        "Recibimos tu mensaje: " + texto +
        "\n\nEscribe PRODUCTOS para consultar algunos articulos."
    )


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
