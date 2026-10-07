from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Bot de joyería funcionando"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Webhook conectado", 200

    data = request.get_json()
    print(data)

    return "EVENT_RECEIVED", 200
