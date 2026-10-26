
from flask import Flask, request, Response, redirect, url_for
import requests
import os
import re
import unicodedata
import time
import secrets
import hmac
import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from html import escape

try:
    import psycopg
except ImportError:
    psycopg = None

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

DOLIBARR_URL = "https://carnevali.dolibarrmnet.com/api/index.php"
DOLIBARR_API_KEY = os.getenv("DOLIBARR_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SALES_VIEW_PASSWORD = os.getenv("SALES_VIEW_PASSWORD")


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


# Memoria temporal por remitente para pruebas de cotizacion.
# Se borra cuando Render reinicia o tras 30 minutos sin actividad.
# Borradores de cotizacion: memoria temporal de una sola instancia.
# Reiniciar Render borra los borradores; no se guardan en Shopify ni Dolibarr.
# Solicitudes completadas se guardan en PostgreSQL externo cuando
# DATABASE_URL y SALES_VIEW_PASSWORD estan configuradas en Render.
# La tabla de solicitudes ya esta creada en Neon.
# El bot solo consulta y guarda registros, nunca modifica el esquema.



def almacenamiento_configurado():
    return bool(DATABASE_URL and SALES_VIEW_PASSWORD and psycopg is not None)


def guardar_solicitud(estado, sender):
    """Guardar solo despues de que el cliente escribe CONFIRMAR."""
    if not almacenamiento_configurado():
        return None

    telefono = "52" + sender[3:] if re.fullmatch(r"521\d{10}", sender) else sender
    folio = f"CAR-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(5).upper()}"
    producto = estado["producto"]

    try:
        with psycopg.connect(
            DATABASE_URL, connect_timeout=8, sslmode="require"
        ) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO solicitudes_cotizacion
                    (folio, producto, referencia, cantidad, ciudad, telefono)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        folio, producto["nombre"], producto.get("ref", ""),
                        estado["cantidad"], estado["ciudad"], telefono
                    )
                )
        return folio
    except Exception as error:
        # No imprimir datos personales ni credenciales.
        print("Error guardando solicitud:", type(error).__name__)
        return None


COTIZACIONES = {}
DURACION_COTIZACION = 30 * 60
MAX_SESIONES = 500


def opciones_cotizacion(estado, descripcion):
    """Consulta Dolibarr antes de permitir seleccionar un modelo."""
    descripcion = descripcion.strip()
    if not 3 <= len(descripcion) <= 120:
        return "Dime el nombre o referencia del producto (3 a 120 caracteres)."

    terminos = obtener_terminos(descripcion)
    if not terminos:
        terminos = re.findall(r"[a-z0-9]{3,}", normalizar(descripcion))[:3]
    if not terminos:
        return "Escribe un nombre o referencia que podamos buscar."

    encontrados = buscar_productos(terminos, limite=60)

    # Si la consulta con varias palabras no encuentra resultados,
    # repetir con la palabra mas especifica: p. ej. 'anillo'.
    if encontrados == [] and len(terminos) > 1:
        encontrados = buscar_productos([terminos[-1]], limite=60)

    if encontrados is None:
        return (
            "Ahora no pude consultar Dolibarr. "
            "Intenta de nuevo con el producto o escribe CANCELAR."
        )

    if not encontrados:
        return (
            "No encontre ese articulo en nuestro catalogo. "
            "Prueba con otro nombre o una referencia. "
            "No voy a inventar un producto."
        )

    referencia_solicitada = normalizar(descripcion)
    referencia_solicitada = re.sub(r"\s+", "", referencia_solicitada)

    def puntuacion(producto):
        nombre = normalizar(producto.get("label") or "")
        referencia = normalizar(producto.get("ref") or "")
        coincide_exacto = referencia == referencia_solicitada
        puntos = sum(1 for t in terminos if t in nombre or t in referencia)
        return (int(coincide_exacto), puntos)

    ordenados = sorted(encontrados, key=puntuacion, reverse=True)
    vistos = set()
    opciones = []

    for p in ordenados:
        ref = str(p.get("ref") or "").strip()
        nombre = str(p.get("label") or ref or "Sin nombre").strip()
        identificador = ref or str(p.get("id") or nombre)

        if identificador in vistos:
            continue
        vistos.add(identificador)
        opciones.append({"nombre": nombre[:140], "ref": ref[:70]})
        if len(opciones) == 5:
            break

    if not opciones:
        return "No encontre modelos con nombre o referencia. Prueba otra busqueda."

    # Solo autoseleccionar un producto si el resultado es unico
    # o la referencia exacta aparece en el catalogo.
    exacto = next(
        (p for p in opciones
         if p["ref"] and normalizar(p["ref"]) == referencia_solicitada),
        None
    )
    if exacto or len(opciones) == 1:
        elegido = exacto or opciones[0]
        estado["producto"] = elegido
        estado.pop("opciones", None)
        estado["paso"] = "cantidad"
        detalle = elegido["nombre"]
        if elegido["ref"]:
            detalle += f" (Ref: {elegido['ref']})"
        return (
            f"Encontré este producto en Dolibarr: {detalle}.\n"
            "¿Cuantas piezas necesitas? (Ejemplo: 100)"
        )

    estado["opciones"] = opciones
    estado["paso"] = "elegir"
    lineas = ["Estos modelos aparecen en Dolibarr:\n"]
    for numero, p in enumerate(opciones, 1):
        referencia = f" (Ref: {p['ref']})" if p["ref"] else ""
        lineas.append(f"{numero}. {p['nombre']}{referencia}")

    lineas.append(
        "\n¿Cuál quieres cotizar? Responde con el número 1-"
        + str(len(opciones))
        + " o escribe su referencia. Si no es ninguno, escribe OTRA."
    )
    return "\n".join(lineas)


def seleccion_de_modelo(texto, estado):
    opciones = estado.get("opciones", [])
    limpio = normalizar(texto.strip())

    if limpio in {"otra", "otro", "ninguna", "ninguno", "otro producto"}:
        estado["paso"] = "producto"
        estado.pop("opciones", None)
        return "Sin problema. ¿Qué otro producto o referencia buscas?"

    numero = None
    seleccion = re.fullmatch(r"(?:la |el |opcion |opcion numero )?([1-5])", limpio)
    if seleccion:
        numero = int(seleccion.group(1))
    else:
        ordinales = {
            "primera": 1, "primero": 1, "segunda": 2, "segundo": 2,
            "tercera": 3, "tercero": 3, "cuarta": 4, "cuarto": 4,
            "quinta": 5, "quinto": 5,
        }
        palabras = limpio.split()
        for palabra in palabras:
            if palabra in ordinales:
                numero = ordinales[palabra]
                break

    elegido = None
    if numero is not None and 1 <= numero <= len(opciones):
        elegido = opciones[numero - 1]
    else:
        for opcion in opciones:
            if opcion["ref"] and normalizar(opcion["ref"]) == limpio:
                elegido = opcion
                break

    if elegido is None:
        return (
            f"Elige un numero del 1 al {len(opciones)} "
            "o una referencia de la lista. Escribe OTRA para buscar de nuevo."
        )

    estado["producto"] = elegido
    estado.pop("opciones", None)
    estado["paso"] = "cantidad"
    detalle = elegido["nombre"]
    if elegido["ref"]:
        detalle += f" (Ref: {elegido['ref']})"
    return f"Perfecto, elegiste {detalle}.\n¿Cuantas piezas necesitas?"


def flujo_cotizacion(texto, sender):
    ahora = time.monotonic()
    for numero, datos in list(COTIZACIONES.items()):
        if ahora - datos["actualizado"] > DURACION_COTIZACION:
            COTIZACIONES.pop(numero, None)

    limpio = normalizar(texto.strip())
    estado = COTIZACIONES.get(sender)

    if limpio in {"cancelar", "salir", "cancelar cotizacion"} and estado:
        COTIZACIONES.pop(sender, None)
        return "Se cancelo el borrador. Puedes escribir COTIZAR de nuevo."

    if not estado:
        palabras = set(re.findall(r"[a-z0-9]+", limpio))
        intencion = {"cotizar", "cotizacion", "cotizaciones",
                     "cotizame", "presupuesto"}
        if not palabras.intersection(intencion):
            return None

        if len(COTIZACIONES) >= MAX_SESIONES:
            antigua = min(
                COTIZACIONES,
                key=lambda clave: COTIZACIONES[clave]["actualizado"]
            )
            COTIZACIONES.pop(antigua, None)

        estado = {"paso": "producto", "actualizado": ahora}
        COTIZACIONES[sender] = estado

        # Admite: "Quiero cotizar cajas para anillos".
        trozos = re.split(
            r"\b(?:cotizar|cotizacion|cotizaciones|cotizame|presupuesto)\b",
            limpio,
            maxsplit=1
        )
        detalle = trozos[-1].strip() if len(trozos) > 1 else ""
        detalle = re.sub(
            r"^(?:de|para|sobre|un|una|unas|unos|el|la|los|las)\s+",
            "", detalle
        ).strip()

        if detalle:
            return opciones_cotizacion(estado, detalle)

        return (
            "¡Claro! 📝 Vamos a preparar un borrador. "
            "No compartimos precios ni enviamos pedidos.\n\n"
            "¿Qué producto o referencia necesitas? "
            "(Escribe CANCELAR cuando quieras)."
        )

    estado["actualizado"] = ahora

    if limpio in {"cotizar", "cotizacion", "cotizaciones"}:
        preguntas = {
            "producto": "¿Qué producto o referencia necesitas?",
            "elegir": "Elige el número del modelo mostrado o su referencia.",
            "cantidad": "¿Cuantas piezas necesitas? (Ejemplo: 100)",
            "ciudad": "¿A qué ciudad sería el envío?",
        }
        return preguntas.get(estado["paso"], "Escribe CANCELAR para comenzar de nuevo.")

    if estado["paso"] == "producto":
        return opciones_cotizacion(estado, texto)

    if estado["paso"] == "elegir":
        return seleccion_de_modelo(texto, estado)

    if estado["paso"] == "cantidad":
        cantidad_match = re.fullmatch(
            r"\s*(\d{1,6})(?:\s*(?:piezas?|unidades?|pz|uds?))?\s*",
            limpio
        )
        if not cantidad_match:
            return "Dime solo la cantidad de piezas. Por ejemplo: 100"

        cantidad = int(cantidad_match.group(1))
        if not 1 <= cantidad <= 100000:
            return "La cantidad debe estar entre 1 y 100000 piezas."

        estado["cantidad"] = cantidad
        estado["paso"] = "ciudad"
        return (
            f"Perfecto, {cantidad} piezas. 📦 "
            "¿A que ciudad seria el envio? No necesitas dar tu direccion."
        )

    if estado["paso"] == "ciudad":
        ciudad = re.sub(r"^(a|en)\s+", "", texto.strip(), flags=re.I).strip()
        if not (2 <= len(ciudad) <= 60 and re.fullmatch(
            r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ .'-]+", ciudad
        )):
            return "Escribe solo la ciudad de destino. Ejemplo: Guadalajara."

        producto = estado["producto"]
        detalle = producto["nombre"]
        if producto["ref"]:
            detalle += f" (Ref: {producto['ref']})"

        resumen = (
            "📝 BORRADOR DE SOLICITUD\n\n"
            f"Producto de Dolibarr: {detalle}\n"
            f"Cantidad: {estado['cantidad']} piezas\n"
            f"Ciudad: {ciudad}\n\n"
            "Este resumen NO es un pedido ni se envio a ventas. "
            "Precio, existencias, envio y personalizacion "
            "estan pendientes de confirmar."
        )
        # En modo de prueba no se almacena nada hasta conectar PostgreSQL.
        if not almacenamiento_configurado():
            COTIZACIONES.pop(sender, None)
            return (
                resumen +
                "\n\nAun NO se guardo en una base de datos. "
                "Primero hay que conectar el almacenamiento de ventas."
            )

        estado["ciudad"] = ciudad
        estado["paso"] = "confirmar"
        return (
            resumen +
            "\n\nSi escribes CONFIRMAR, guardaremos este borrador y "
            "tu numero de WhatsApp para que ventas pueda revisarlo. "
            "No crea pedidos ni calcula precios. "
            "Escribe CANCELAR si no deseas guardarlo."
        )

    if estado["paso"] == "confirmar":
        if limpio not in {"confirmar", "confirmo", "si confirmo"}:
            return "Escribe CONFIRMAR para guardar o CANCELAR para descartar."

        folio = guardar_solicitud(estado, sender)
        if folio is None:
            return (
                "No fue posible guardar la solicitud. "
                "No hay folio registrado. "
                "Escribe CONFIRMAR para reintentar o CANCELAR."
            )

        COTIZACIONES.pop(sender, None)
        return (
            f"✅ Solicitud guardada con folio {folio}.\n"
            "Ventas podra revisarla en su panel privado. "
            "Esto no es un pedido ni una cotizacion con precio confirmado."
        )

    COTIZACIONES.pop(sender, None)
    return "Vamos a empezar de nuevo. Escribe COTIZAR."


def preparar_respuesta(texto, sender=None):
    texto_limpio = normalizar(texto.strip())

    if sender:
        respuesta_cotizacion = flujo_cotizacion(texto, sender)
        if respuesta_cotizacion is not None:
            return respuesta_cotizacion

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


ESTADOS_VENTAS = {
    "nuevo": "Nueva",
    "en_revision": "En revisión",
    "atendido": "Atendida"
}


def _cabeceras_privadas(respuesta):
    """Evita cacheos y acceso del buscador al panel de datos personales."""
    respuesta.headers["Cache-Control"] = "no-store, max-age=0"
    respuesta.headers["Pragma"] = "no-cache"
    respuesta.headers["X-Robots-Tag"] = "noindex, nofollow"
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    return respuesta


def _acceso_ventas():
    """Autorización común para consultar y modificar el panel."""
    if not almacenamiento_configurado():
        return _cabeceras_privadas(
            Response("Panel sin configurar.", status=503)
        )

    auth = request.authorization
    usuario = auth.username if auth and auth.type == "basic" else ""
    clave = auth.password if auth and auth.type == "basic" else ""
    if not (
        secrets.compare_digest(usuario or "", "ventas")
        and secrets.compare_digest(clave or "", SALES_VIEW_PASSWORD)
    ):
        return _cabeceras_privadas(Response(
            "Acceso restringido a ventas.",
            status=401,
            headers={"WWW-Authenticate": 'Basic realm="Carnevali Ventas"'}
        ))

    return None


def _token_ventas(folio, ventana=None):
    """Token anti-CSRF de validez corta, sin cookies ni sesiones."""
    if ventana is None:
        ventana = int(time.time() // 1800)
    datos = f"estado:{folio}:{ventana}".encode("utf-8")
    return hmac.new(
        SALES_VIEW_PASSWORD.encode("utf-8"), datos, hashlib.sha256
    ).hexdigest()


def _validar_token_ventas(folio, token):
    if not isinstance(token, str) or len(token) != 64:
        return False
    ventana = int(time.time() // 1800)
    return any(
        hmac.compare_digest(token, _token_ventas(folio, v))
        for v in (ventana, ventana - 1)
    )


def _formato_fecha_ventas(fecha):
    if fecha is None:
        return ""
    try:
        return fecha.astimezone(
            ZoneInfo("America/Monterrey")
        ).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return ""


@app.route("/ventas", methods=["GET"])
def panel_ventas():
    error_acceso = _acceso_ventas()
    if error_acceso is not None:
        return error_acceso

    busqueda = request.args.get("q", "")[:80].strip()
    filtro = request.args.get("estado", "todos")
    if filtro not in (*ESTADOS_VENTAS.keys(), "todos"):
        filtro = "todos"

    try:
        pagina = max(1, min(int(request.args.get("pagina", "1")), 100))
    except ValueError:
        pagina = 1
    limite = 30

    condiciones, parametros = [], []
    if busqueda:
        patron = "%" + busqueda + "%"
        condiciones.append(
            "(folio ILIKE %s OR producto ILIKE %s OR "
            "referencia ILIKE %s OR ciudad ILIKE %s)"
        )
        parametros.extend([patron] * 4)

    if filtro != "todos":
        condiciones.append("estado = %s")
        parametros.append(filtro)

    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""

    try:
        with psycopg.connect(
            DATABASE_URL, connect_timeout=8, sslmode="require"
        ) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT estado, COUNT(*) "
                    "FROM solicitudes_cotizacion GROUP BY estado"
                )
                conteos = {
                    estado: cantidad for estado, cantidad in cursor.fetchall()
                }

                cursor.execute(
                    "SELECT COUNT(*) FROM solicitudes_cotizacion" + where,
                    parametros
                )
                total = cursor.fetchone()[0]
                paginas = max(1, (total + limite - 1) // limite)
                pagina = min(pagina, paginas)

                cursor.execute(
                    "SELECT folio, producto, referencia, cantidad, "
                    "ciudad, telefono, estado, creada_en "
                    "FROM solicitudes_cotizacion" + where +
                    " ORDER BY creada_en DESC, folio DESC "
                    "LIMIT %s OFFSET %s",
                    parametros + [limite, (pagina - 1) * limite]
                )
                solicitudes = cursor.fetchall()
    except Exception as error:
        print("Error consultando panel:", type(error).__name__)
        return _cabeceras_privadas(Response(
            "No se pudo consultar Neon. Intenta de nuevo.", status=503
        ))

    def e(valor):
        return escape(str(valor if valor is not None else ""), quote=True)

    def enlace_pagina(n):
        return url_for(
            "panel_ventas", q=busqueda, estado=filtro, pagina=n
        )

    opciones_filtro = ['<option value="todos">Todos los estados</option>']
    for key, texto in ESTADOS_VENTAS.items():
        marcado = " selected" if filtro == key else ""
        opciones_filtro.append(
            f'<option value="{key}"{marcado}>{e(texto)}</option>'
        )
    if filtro == "todos":
        opciones_filtro[0] = '<option value="todos" selected>Todos los estados</option>'

    filas = []
    for folio, producto, referencia, cantidad, ciudad, telefono, estado, fecha in solicitudes:
        etiqueta = ESTADOS_VENTAS.get(estado, e(estado))
        opciones = []
        for k, nombre in ESTADOS_VENTAS.items():
            marcado = " selected" if estado == k else ""
            opciones.append(
                f'<option value="{k}"{marcado}>{e(nombre)}</option>'
            )

        token = _token_ventas(str(folio))
        formulario = (
            '<form method="post" action="/ventas/estado" class="accion">'
            f'<input type="hidden" name="folio" value="{e(folio)}">'
            f'<input type="hidden" name="csrf" value="{token}">'
            f'<input type="hidden" name="q" value="{e(busqueda)}">'
            f'<input type="hidden" name="filtro" value="{e(filtro)}">'
            f'<input type="hidden" name="pagina" value="{pagina}">'
            '<label class="sr-only" for="estado-' + e(folio) +
            '">Estado de solicitud</label>'
            '<select id="estado-' + e(folio) +
            '" name="estado">' + "".join(opciones) + '</select>'
            '<button type="submit">Guardar</button></form>'
        )
        filas.append(
            '<tr>'
            f'<td><b>{e(folio)}</b><div class="muted">{e(_formato_fecha_ventas(fecha))}</div></td>'
            f'<td>{e(producto)}<div class="muted">Ref: {e(referencia)}</div></td>'
            f'<td class="numero">{e(cantidad)}</td>'
            f'<td>{e(ciudad)}</td>'
            f'<td><a href="https://wa.me/{e(telefono)}" '
            f'rel="noreferrer" target="_blank">{e(telefono)}</a></td>'
            f'<td><span class="chip estado-{e(estado)}">{e(etiqueta)}</span>'
            f'{formulario}</td>'
            '</tr>'
        )

    if filas:
        tabla = "".join(filas)
    else:
        tabla = '<tr><td colspan="6" class="vacio">No hay solicitudes con esos filtros.</td></tr>'

    total_general = sum(conteos.values())
    tarjetas = [
        ("Todas", total_general),
        ("Nuevas", conteos.get("nuevo", 0)),
        ("En revisión", conteos.get("en_revision", 0)),
        ("Atendidas", conteos.get("atendido", 0)),
    ]
    resumen_html = "".join(
        f'<div class="stat"><span>{e(titulo)}</span><strong>{e(cantidad)}</strong></div>'
        for titulo, cantidad in tarjetas
    )
    boton_anterior = (
        f'<a href="{e(enlace_pagina(pagina - 1))}">Anterior</a>'
        if pagina > 1 else '<span class="desactivado">Anterior</span>'
    )
    boton_siguiente = (
        f'<a href="{e(enlace_pagina(pagina + 1))}">Siguiente</a>'
        if pagina < paginas else '<span class="desactivado">Siguiente</span>'
    )
    aviso = (
        '<p class="exito">Estado actualizado correctamente.</p>'
        if request.args.get("actualizado") == "1" else ""
    )

    pagina_html = """
    <!doctype html>
    <html lang="es"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Carnevali | Panel de cotizaciones</title>
    <style>
    :root {color-scheme:light;font-family:system-ui,-apple-system,sans-serif}
    *{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:#182330}
    .wrap{max-width:1220px;margin:auto;padding:28px 20px 70px}
    h1{font-size:clamp(24px,3vw,34px);letter-spacing:-.6px;margin:4px 0}
    h2{font-size:17px;margin:0}p{color:#586577;margin:6px 0 18px}
    .top{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
    .pill{background:#ebf3ee;color:#17643f;font-size:12px;border-radius:20px;padding:8px 12px}
    .stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:22px 0}
    .stat{background:#fff;border:1px solid #e1e5eb;border-radius:12px;padding:18px}
    .stat span{display:block;color:#637183;font-size:13px}
    .stat strong{display:block;font-size:30px;margin-top:3px}
    .panel{background:#fff;border:1px solid #e1e5eb;border-radius:12px;overflow:hidden}
    .toolbar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;padding:18px}
    .buscar{display:flex;flex-wrap:wrap;gap:8px}
    input,select,button{font:inherit;padding:9px 11px;border:1px solid #d2d9e2;border-radius:8px;background:white}
    button{background:#173a57;color:white;border-color:#173a57;cursor:pointer}
    input[type="search"]{width:min(270px,70vw)}
    table{border-collapse:collapse;width:100%;min-width:900px;font-size:13px}
    th,td{padding:15px;text-align:left;border-top:1px solid #ebeff3;vertical-align:top}
    th{background:#f9fafb;color:#5b6776;font-weight:600}
    .scroll{overflow:auto}.muted{font-size:12px;color:#6d7786;margin-top:5px}
    .numero{font-variant-numeric:tabular-nums}
    .chip{display:inline-block;border-radius:20px;padding:5px 9px;background:#f1f3f6;color:#425167}
    .estado-nuevo{background:#edf3ff;color:#2258a6}
    .estado-en_revision{background:#fff4de;color:#86551b}
    .estado-atendido{background:#eaf7ee;color:#17643f}
    .accion{display:flex;gap:5px;margin-top:9px;white-space:nowrap}
    .accion select,.accion button{font-size:12px;padding:7px}
    .pagination{display:flex;justify-content:space-between;padding:17px;gap:12px;align-items:center;color:#627084}
    .pagination a{color:#194a75;text-decoration:none;font-weight:600;padding:8px}
    .desactivado{opacity:.35}.vacio{text-align:center;padding:45px;color:#6b7788}
    .exito{background:#eaf7ee;color:#17643f;padding:12px 16px;border-radius:9px}
    .nota{font-size:12px;color:#6b7788;margin-top:14px}
    .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
    a{color:#1a5687}
    @media(max-width:650px){.wrap{padding:18px 12px 48px}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}
      .stat{padding:13px}.stat strong{font-size:25px}.toolbar{padding:13px}.buscar{width:100%}}
    </style></head><body><main class="wrap">
    <header class="top"><div><h1>Carnevali Estuches</h1>
    <p>Panel privado de solicitudes de cotización</p></div>
    <span class="pill">Conectado a Neon</span></header>
    """ + aviso + """
    <div class="stats">""" + resumen_html + """</div>
    <section class="panel">
    <div class="toolbar"><h2>Solicitudes</h2>
    <form method="get" action="/ventas" class="buscar">
    <label class="sr-only" for="q">Buscar solicitud</label>
    <input id="q" type="search" name="q"
       placeholder="Buscar folio, producto, referencia, ciudad"
       value='""" + e(busqueda) + """'>
    <label class="sr-only" for="estado">Filtrar por estado</label>
    <select id="estado" name="estado">""" + "".join(opciones_filtro) + """</select>
    <button type="submit">Buscar</button></form></div>
    <div class="scroll"><table><thead><tr>
    <th>Folio / fecha</th><th>Producto</th><th>Piezas</th>
    <th>Destino</th><th>WhatsApp</th><th>Estado / acción</th>
    </tr></thead><tbody>""" + tabla + """</tbody></table></div>
    <div class="pagination"><span>""" + e(total) + """ resultado(s)</span>
    <div>""" + boton_anterior + f" Página {pagina} de {paginas} " + boton_siguiente + """</div></div>
    </section>
    <p class="nota">Fechas de Monterrey. No son pedidos ni cotizaciones con precios
    confirmados. Cambiar un estado aquí no manda mensajes al cliente.</p>
    </main></body></html>"""

    return _cabeceras_privadas(
        Response(pagina_html, status=200, mimetype="text/html")
    )


@app.route("/ventas/estado", methods=["POST"])
def actualizar_estado_venta():
    error_acceso = _acceso_ventas()
    if error_acceso is not None:
        return error_acceso

    folio = request.form.get("folio", "")[:48]
    estado = request.form.get("estado", "")
    token = request.form.get("csrf", "")

    if not re.fullmatch(r"CAR-\d{8}-[A-Z0-9]{10}", folio):
        return _cabeceras_privadas(Response("Folio inválido.", status=400))
    if estado not in ESTADOS_VENTAS or not _validar_token_ventas(folio, token):
        return _cabeceras_privadas(Response("Operación no autorizada.", status=403))

    try:
        with psycopg.connect(
            DATABASE_URL, connect_timeout=8, sslmode="require"
        ) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "UPDATE solicitudes_cotizacion SET estado = %s "
                    "WHERE folio = %s RETURNING folio",
                    (estado, folio)
                )
                actualizado = cursor.fetchone()
        if not actualizado:
            return _cabeceras_privadas(
                Response("No encontramos ese folio.", status=404)
            )
    except Exception as error:
        print("Error al actualizar estado:", type(error).__name__)
        return _cabeceras_privadas(
            Response("No se pudo guardar el estado.", status=503)
        )

    filtro = request.form.get("filtro", "todos")
    if filtro not in (*ESTADOS_VENTAS.keys(), "todos"):
        filtro = "todos"
    busqueda = request.form.get("q", "")[:80]
    try:
        pagina = max(1, min(int(request.form.get("pagina", "1")), 100))
    except ValueError:
        pagina = 1

    redireccion = url_for(
        "panel_ventas", q=busqueda, estado=filtro,
        pagina=pagina, actualizado="1"
    )
    return _cabeceras_privadas(redirect(redireccion, code=303))


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

            respuesta_bot = preparar_respuesta(texto, sender)

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
