"""Flujo experimental de cotizaciones con varios productos por WhatsApp.

La API de Dolibarr, el teléfono y PostgreSQL se inyectan desde app.py.
Solo se activará con CARRITO_MULTIPRODUCTO=1, tras instalar la migración.
"""

import re
import time
import unicodedata

from carrito_cotizacion import (
    agregar_linea, cambiar_cantidad, extraer_lotes, quitar_linea,
    resumen_carrito, validar_cantidad,
)

SESIONES = {}
TIEMPO_MAXIMO = 30 * 60
MAX_SESIONES = 500


def _norm(texto):
    s = unicodedata.normalize("NFD", str(texto).casefold())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _terminos(texto):
    ruido = {
        "quiero", "para", "caja", "cajas", "de", "del", "unos", "unas",
        "el", "la", "los", "las", "por", "favor", "necesito", "cotizar",
        "cotizacion", "piezas", "producto", "productos", "un", "una",
    }
    resultado = []
    for palabra in re.findall(r"[a-z0-9]+", _norm(texto)):
        if palabra in ruido or len(palabra) < 3:
            continue
        if palabra == "relojes":
            palabra = "reloj"
        elif palabra.endswith("es") and len(palabra) > 5:
            palabra = palabra[:-2]
        elif palabra.endswith("s") and len(palabra) > 4:
            palabra = palabra[:-1]
        if palabra not in resultado:
            resultado.append(palabra)
    return resultado[:4]


def _descripcion_producto(producto):
    detalle = producto["nombre"]
    if producto.get("ref"):
        detalle += f" (Ref: {producto['ref']})"
    return detalle


def _controles(items):
    return (
        resumen_carrito(items)
        + "\n\nPuedes escribir AGREGAR, VER, QUITAR 2, CAMBIAR 2 80, "
          "LISTO o CANCELAR."
    )


def _buscar_producto(estado, descripcion, buscar, obtener_terminos):
    descripcion = descripcion.strip()
    if not 3 <= len(descripcion) <= 120:
        return "Dime el nombre o referencia del producto (3 a 120 caracteres)."
    terminos = obtener_terminos(descripcion)
    if not terminos:
        terminos = _terminos(descripcion)
    if not terminos:
        return "Escribe el nombre o referencia del producto que necesitas."
    encontrados = buscar(terminos, limite=60)
    if encontrados == [] and len(terminos) > 1:
        encontrados = buscar([terminos[-1]], limite=60)
    if encontrados == []:
        variantes = _terminos(descripcion)
        if variantes and variantes != terminos:
            encontrados = buscar(variantes, limite=60)
    if encontrados is None:
        return "No pude consultar Dolibarr. Intenta de nuevo o escribe CANCELAR."
    if not encontrados:
        return "No encontré ese producto. Prueba con otro nombre o referencia."

    descripcion_ref = re.sub(r"\s+", "", _norm(descripcion))

    def relevancia(p):
        label = _norm(p.get("label") or "")
        ref = _norm(p.get("ref") or "")
        return (int(ref == descripcion_ref), sum(v in label or v in ref for v in terminos))

    opciones, vistos = [], set()
    for p in sorted(encontrados, key=relevancia, reverse=True):
        ref = str(p.get("ref") or "").strip()[:70]
        nombre = str(p.get("label") or ref).strip()[:140]
        clave = ref.casefold() or _norm(nombre)
        if not nombre or clave in vistos:
            continue
        vistos.add(clave)
        opciones.append({"nombre": nombre, "ref": ref})
        if len(opciones) == 5:
            break
    if not opciones:
        return "No encontré modelos con nombre o referencia válidos."

    estado["opciones"] = opciones
    estado["paso"] = "elegir"
    if len(opciones) == 1 or any(_norm(p["ref"]) == descripcion_ref for p in opciones if p["ref"]):
        seleccionado = next((p for p in opciones if p["ref"] and _norm(p["ref"]) == descripcion_ref), opciones[0])
        return _seleccionar_producto(estado, seleccionado, buscar, obtener_terminos)

    lineas = ["Encontré estos modelos en Dolibarr:"]
    for num, p in enumerate(opciones, 1):
        lineas.append(f"{num}. {_descripcion_producto(p)}")
    lineas.append("\n¿Cuál quieres? Escribe un número o la referencia; OTRA para buscar de nuevo.")
    return "\n".join(lineas)


def _siguiente_pendiente(estado, buscar, obtener_terminos):
    pendientes = estado.get("pendientes", [])
    if pendientes:
        siguiente = pendientes.pop(0)
        estado["cantidad_sugerida"] = siguiente["cantidad"]
        return "Continuamos con el siguiente producto:\n" + _buscar_producto(
            estado, siguiente["descripcion"], buscar, obtener_terminos
        )
    estado["paso"] = "carrito"
    estado.pop("cantidad_sugerida", None)
    estado.pop("producto", None)
    return _controles(estado["items"])


def _agregar_seleccion(estado, producto, cantidad, buscar, obtener_terminos):
    try:
        agregar_linea(estado["items"], producto, cantidad)
    except ValueError as error:
        estado["paso"] = "carrito"
        estado.pop("pendientes", None)
        return f"No pude agregar ese producto: {error}\n\n{_controles(estado['items'])}"
    return (
        f"✅ Agregué {_descripcion_producto(producto)}: {cantidad} piezas.\n\n"
        + _siguiente_pendiente(estado, buscar, obtener_terminos)
    )


def _seleccionar_producto(estado, producto, buscar, obtener_terminos):
    estado.pop("opciones", None)
    cantidad = estado.pop("cantidad_sugerida", None)
    if cantidad is not None:
        return _agregar_seleccion(estado, producto, cantidad, buscar, obtener_terminos)
    estado["producto"] = producto
    estado["paso"] = "cantidad"
    return f"Elegiste {_descripcion_producto(producto)}. ¿Cuántas piezas necesitas?"


def _elegir(estado, texto, buscar, obtener_terminos):
    limpio = _norm(texto).strip()
    if limpio in {"otra", "otro", "ninguna", "ninguno"}:
        estado["paso"] = "producto"
        estado.pop("opciones", None)
        estado.pop("cantidad_sugerida", None)
        estado.pop("pendientes", None)
        return "¿Qué otro producto buscas?"
    seleccion = re.fullmatch(r"(?:la |el |opcion |opcion numero )?([1-5])", limpio)
    numero = int(seleccion.group(1)) if seleccion else None
    if numero is None:
        orden = {"primera": 1, "primero": 1, "segunda": 2, "segundo": 2,
                 "tercera": 3, "tercero": 3, "cuarta": 4, "cuarto": 4,
                 "quinta": 5, "quinto": 5}
        for palabra in limpio.split():
            if palabra in orden:
                numero = orden[palabra]
                break
    opciones = estado.get("opciones", [])
    producto = opciones[numero - 1] if numero and 1 <= numero <= len(opciones) else None
    if producto is None:
        producto = next((p for p in opciones if p["ref"] and _norm(p["ref"]) == limpio), None)
    if producto is None:
        return "Elige una opción de la lista por número o referencia; escribe OTRA para buscar de nuevo."
    return _seleccionar_producto(estado, producto, buscar, obtener_terminos)


def _iniciar_busqueda(estado, texto, buscar, obtener_terminos):
    lotes = extraer_lotes(texto)
    if lotes:
        estado["pendientes"] = lotes[1:]
        estado["cantidad_sugerida"] = lotes[0]["cantidad"]
        return _buscar_producto(estado, lotes[0]["descripcion"], buscar, obtener_terminos)
    estado.pop("cantidad_sugerida", None)
    estado.pop("pendientes", None)
    descripcion = re.sub(
        r"^(?:(?:quiero|quisiera|necesito)\s+)?"
        r"(?:cotizar|agregar|agrega|añadir|anadir)\s*",
        "", texto.strip(), flags=re.I
    ).strip()
    descripcion = re.sub(r"^(?:de|para|un|una|unas|unos|el|la|los|las)\s+", "", descripcion, flags=re.I)
    if not descripcion:
        estado["paso"] = "producto"
        return "¿Qué producto o referencia quieres agregar? Puedes decir: 100 cajas para anillos."
    return _buscar_producto(estado, descripcion, buscar, obtener_terminos)


def manejar_carrito(sender, texto, buscar, obtener_terminos, guardar, disponible):
    """Devuelve respuesta, o None si no pertenece a un carrito.

    guardar(items, ciudad, sender) confirma transaccionalmente en Neon.
    Ninguna solicitud se guarda sin escribir CONFIRMAR explícitamente.
    """
    ahora = time.monotonic()
    for numero, s in list(SESIONES.items()):
        if ahora - s["actualizado"] > TIEMPO_MAXIMO:
            SESIONES.pop(numero, None)
    limpio = _norm(texto).strip()
    estado = SESIONES.get(sender)
    if estado is None:
        if not re.search(r"\b(cotizar|cotizacion|cotizame|presupuesto|carrito)\b", limpio):
            return None
        if len(SESIONES) >= MAX_SESIONES:
            antiguo = min(SESIONES, key=lambda k: SESIONES[k]["actualizado"])
            SESIONES.pop(antiguo, None)
        estado = {"paso": "producto", "items": [], "actualizado": ahora}
        SESIONES[sender] = estado
        return "📝 Vamos a preparar una cotización con varios productos.\n" + _iniciar_busqueda(
            estado, texto, buscar, obtener_terminos
        )

    estado["actualizado"] = ahora
    if limpio in {"cancelar", "salir", "cancelar cotizacion"}:
        SESIONES.pop(sender, None)
        return "Cancelé el carrito. No envié ni guardé ninguna solicitud."
    if limpio in {"ver", "ver carrito", "carrito", "resumen"}:
        return _controles(estado["items"])

    paso = estado["paso"]
    if paso == "producto":
        return _iniciar_busqueda(estado, texto, buscar, obtener_terminos)
    if paso == "elegir":
        return _elegir(estado, texto, buscar, obtener_terminos)
    if paso == "cantidad":
        cantidad = validar_cantidad(texto)
        if cantidad is None:
            return "Dime solo la cantidad, por ejemplo: 100 piezas."
        return _agregar_seleccion(estado, estado.pop("producto"), cantidad, buscar, obtener_terminos)
    if paso == "carrito":
        if limpio in {"agregar", "anadir", "añadir", "otro producto"}:
            estado["paso"] = "producto"
            return "¿Qué producto o referencia quieres agregar?"
        if limpio.startswith(("agregar ", "agrega ", "anadir ", "añadir ")) or extraer_lotes(texto):
            return _iniciar_busqueda(estado, texto, buscar, obtener_terminos)
        quitar = re.fullmatch(r"(?:quitar|eliminar|borrar)\s+(\d{1,2})", limpio)
        if quitar:
            try:
                retirado = quitar_linea(estado["items"], int(quitar.group(1)))
                return f"Quité {retirado['nombre']}.\n\n" + _controles(estado["items"])
            except ValueError as error:
                return str(error) + "\n\n" + _controles(estado["items"])
        cambiar = re.fullmatch(r"(?:cambiar|modificar)\s+(\d{1,2})\s+(\d{1,6})", limpio)
        if cambiar:
            try:
                item = cambiar_cantidad(estado["items"], int(cambiar.group(1)), int(cambiar.group(2)))
                return f"Cantidad cambiada: {item['nombre']} — {item['cantidad']} piezas.\n\n" + _controles(estado["items"])
            except ValueError as error:
                return str(error) + "\n\n" + _controles(estado["items"])
        if limpio in {"listo", "terminar", "finalizar", "ya es todo"}:
            if not estado["items"]:
                return "El carrito está vacío. Primero escribe AGREGAR."
            estado["paso"] = "ciudad"
            return "Perfecto. ¿A qué ciudad sería el envío? (No necesitas tu dirección)."
        return "No entendí esa acción.\n\n" + _controles(estado["items"])

    if paso == "ciudad":
        ciudad = re.sub(r"^(?:a|en)\s+", "", texto.strip(), flags=re.I).strip()
        if not (2 <= len(ciudad) <= 60 and re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ .'-]+", ciudad)):
            return "Dime solo la ciudad, por ejemplo: Guadalajara."
        estado["ciudad"] = ciudad
        estado["paso"] = "confirmar"
        return (
            resumen_carrito(estado["items"]) + f"\nDestino: {ciudad}\n\n"
            "Esto NO es un pedido ni incluye precios o existencias confirmadas. "
            "Si escribes CONFIRMAR, guardaremos esta solicitud y tu número "
            "de WhatsApp para que ventas la revise. Escribe CANCELAR para descartarla."
        )
    if paso == "confirmar":
        if limpio not in {"confirmar", "confirmo", "si confirmo"}:
            return "Escribe CONFIRMAR para guardar o CANCELAR para descartar."
        if not disponible():
            return "Todavía no está habilitado el guardado del carrito. No se creó ningún folio."
        folio = guardar(estado["items"], estado["ciudad"], sender)
        if not folio:
            return "No pude guardar la solicitud. No hay folio nuevo. Escribe CONFIRMAR para reintentar."
        SESIONES.pop(sender, None)
        return (
            f"✅ Solicitud multiproducto guardada con folio {folio}. "
            "Ventas podrá revisarla en el panel. "
            "Precios y existencias quedan pendientes de confirmar."
        )
    SESIONES.pop(sender, None)
    return "Escribe COTIZAR para iniciar un carrito nuevo."
