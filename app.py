from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = "joyeria123"

@app.route("/", methods=["GET"])
def home():
    return "Bot de joyería funcionando", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200

        return "Verification failed", 403

    data = request.get_json()
    print(data)

    return "EVENT_RECEIVED", 200
