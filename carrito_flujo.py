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
        "quiero", "quisiera", "necesito", "ocupo", "busco", "buscar",
        "para", "de", "del", "unos", "unas", "los", "las", "por", "favor",
        "cotizar", "cotizacion", "piezas", "producto", "productos",
        "un", "una", "dame", "agrega", "agregar", "agregame", "otros",
        "otro", "otras", "otra", "me", "que", "son", "quieres",
    }
    plurales = {
        "estuches": "estuche", "cajas": "caja",
        "anillos": "anillo", "aretes": "arete",
        "pulseras": "pulsera", "collares": "collar",
        "cadenas": "cadena", "relojes": "reloj",
    }
    normalizado = _norm(texto).strip()
    # Preservar referencias como 1481.NB o 3042-CH al buscarlas.
    if re.fullmatch(r"[a-z0-9]+[._-][a-z0-9._-]+", normalizado):
        return [normalizado]
    resultado = []
    for palabra in re.findall(r"[a-z0-9]+", normalizado):
        palabra = plurales.get(palabra, palabra)
        if palabra in ruido or len(palabra) < 3:
            continue
        if palabra not in resultado:
            resultado.append(palabra)
    return resultado[:5]


def _limpiar_descripcion(texto, estado):
    """Quita cortesías sin borrar la cantidad del artículo solicitado."""
    s = _norm(texto).strip()
    s = re.sub(
        r"^(?:(?:pero|oye|mira)\s+)?"
        r"(?:(?:quiero|necesito|quisiera|ocupo|busco|buscame|buscame|"
        r"agregame|agrega|agregar|muestrame|dame)\s+)+", "", s
    )
    s = re.sub(r"^(?:unas?|unos?|las?|los?)\s+", "", s)
    cantidad = re.match(r"^(\d{1,6})\s+(.+)$", s)
    if cantidad:
        numero = int(cantidad.group(1))
        if 1 <= numero <= 100000:
            # El número explícito prevalece sobre la cantidad sugerida.
            estado["cantidad_sugerida"] = numero
            s = cantidad.group(2)
    s = re.sub(r"^(?:de|del|para|unas?|unos?|las?|los?)\s+", "", s)
    return s.strip()


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
    descripcion = _limpiar_descripcion(descripcion, estado)
    if not 3 <= len(descripcion) <= 120:
        estado["paso"] = "producto"
        return "Dime qué producto buscas, por ejemplo: estuches para aretes rojos."

    palabras = _terminos(descripcion)
    if not palabras:
        estado["paso"] = "producto"
        return "¿Qué tipo de caja o estuche necesitas?"

    referencia_buscada = re.sub(r"\s+", "", _norm(descripcion))
    empaque = any(t in palabras for t in ("caja", "estuche"))
    uso = [t for t in palabras if t in {"anillo", "arete", "pulsera", "collar", "reloj"}]
    color = [t for t in palabras if t in {
        "rojo", "roja", "azul", "negro", "negra", "blanco", "blanca",
        "rosa", "dorado", "dorada", "verde", "plateado", "plateada"
    }]
    # Intentamos coincidencias estrictas y después una búsqueda más amplia.
    # El filtro local sigue rechazando referencias de otro tipo de producto.
    consultas = [palabras[:4]]
    if uso:
        consultas.append(uso + color)
        consultas.append(uso)
    elif empaque:
        consultas.append(["caja"] if "caja" in palabras else ["estuche"])
    else:
        consultas.append(palabras[-1:])
    consultas = [q for i, q in enumerate(consultas) if q and q not in consultas[:i]]
    encontrados = []
    vistos = set()
    fallo_api = False
    for consulta in consultas[:3]:
        # Los términos ya están normalizados y son filtrados por buscar_productos.
        respuesta = buscar(consulta, limite=100)
        if respuesta is None:
            fallo_api = True
            break
        for p in respuesta:
            ref = str(p.get("ref") or "").strip()
            nombre = str(p.get("label") or ref).strip()
            key = ref.casefold() or _norm(nombre)
            if key in vistos or not nombre:
                continue
            vistos.add(key)
            encontrados.append({"nombre": nombre[:140], "ref": ref[:70]})
        # Si hay candidatos suficientes, no necesitamos más llamadas a Dolibarr.
        if len(encontrados) >= 75:
            break

    if fallo_api and not encontrados:
        estado["paso"] = "producto"
        return "No pude consultar Dolibarr. Intenta otra vez o pide un vendedor."

    def pasa_filtro(p):
        label = _norm(p["nombre"])
        ref = _norm(p["ref"])
        if ref == referencia_buscada and ref:
            return True
        tokens = set(re.findall(r"[a-z0-9]+", label))
        if empaque and not tokens.intersection({"caja", "cajas", "estuche", "estuches"}):
            return False
        if any(not any(t == u or t.startswith(u) for t in tokens) for u in uso):
            return False
        if color and not any(t in tokens for t in color):
            return False
        if not empaque and not uso and not color:
            if not any(t in label or t in ref for t in palabras):
                return False
        return True

    opciones = [p for p in encontrados if pasa_filtro(p)]
    if not opciones:
        estado["paso"] = "producto"
        descripcion_tipo = (
            "cajas o estuches con esas características" if empaque
            else "productos con esas características"
        )
        return (
            f"No encontré {descripcion_tipo} en los resultados del catálogo. "
            "No quiero ofrecerte un artículo distinto por error. "
            "Prueba otra descripción o referencia, o solicita ayuda a ventas."
        )

    def relevancia(p):
        label = _norm(p["nombre"])
        ref = _norm(p["ref"])
        return (
            int(ref == referencia_buscada),
            sum(t in label or t in ref for t in palabras),
            int("estuche" in label or "caja" in label),
        )

    opciones = sorted(opciones, key=relevancia, reverse=True)[:5]
    estado["opciones"] = opciones
    estado["paso"] = "elegir"
    # Una búsqueda genérica nunca debe agregar automáticamente el único
    # resultado. Solo una referencia explícita y exacta autoriza elegirlo.
    if any(p["ref"] and _norm(p["ref"]) == referencia_buscada for p in opciones):
        elegido = next(p for p in opciones if p["ref"] and _norm(p["ref"]) == referencia_buscada)
        return _seleccionar_producto(estado, elegido, buscar, obtener_terminos)

    lineas = ["Encontré estas opciones en el catálogo de Carnevali:"]
    lineas.extend(f"{num}. {_descripcion_producto(p)}" for num, p in enumerate(opciones, 1))
    lineas.append(
        "\n¿Cuál modelo buscas? Escribe su número o referencia. "
        "Si no es ninguno, dime qué característica deseas cambiar."
    )
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
    limpio = _norm(texto).strip(" ¿?!.,")
    if re.search(r"\b(fotos?|fotografias?|imagenes?|imagen|ver fotos?)\b", limpio):
        return (
            "Todavía no tengo fotografías verificadas para mandar por WhatsApp. "
            "No quiero mostrarte una foto equivocada. "
            "Puedes pedir imágenes al equipo de ventas indicando la referencia. "
            "Estas son las opciones que encontré:\n" +
            "\n".join(
                f"{i}. {_descripcion_producto(p)}"
                for i, p in enumerate(estado.get("opciones", []), 1)
            ) + "\n¿Cuál referencia te interesa?"
        )
    if limpio in {
        "esto que es", "esto que es?", "que productos son",
        "que productos son?", "que es eso", "que es",
        "que opciones son", "explicame los productos",
    }:
        return (
            "Son resultados del catálogo de Dolibarr, pero pueden incluir "
            "modelos distintos. Para evitar confundirte, aquí están los "
            "nombres exactos que tengo:\n" +
            "\n".join(
                f"{i}. {_descripcion_producto(p)}"
                for i, p in enumerate(estado.get("opciones", []), 1)
            ) +
            "\nSi ninguno es el tipo de producto que quieres, "
            "dime por ejemplo: NECESITO CAJAS PARA ARETES."
        )
    # Una aclaración del tipo de producto inicia una búsqueda corregida,
    # sin perder la cantidad ya indicada ni los demás renglones pendientes.
    if re.search(r"\b(?:necesito|ocupo|busco|buscame|quiero|pero)\b", limpio) and any(
        t in _terminos(limpio)
        for t in ("anillo", "arete", "pulsera", "collar", "estuche", "caja", "reloj")
    ):
        return _buscar_producto(estado, texto, buscar, obtener_terminos)
    if limpio in {"otra", "otro", "ninguna", "ninguno"}:
        estado["paso"] = "producto"
        estado.pop("opciones", None)
        # OTRA cambia el modelo que se está buscando, no la cantidad solicitada
        # ni los demás artículos pendientes del mensaje original.
        cantidad_pendiente = estado.get("cantidad_sugerida")
        if cantidad_pendiente is not None:
            return (
                f"Claro. Mantengo {cantidad_pendiente} piezas de este artículo "
                "y los demás productos de tu solicitud. "
                "¿Qué otro modelo o referencia buscas?"
            )
        return "¿Qué otro producto o referencia buscas?"
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


def _reponer_articulo_omitido(estado, texto, buscar, obtener_terminos):
    """Recupera un artículo omitido con cantidad numérica explícita.

    Solicita elegir la referencia real antes de añadirlo al carrito.
    """
    limpio = _norm(texto).strip()
    patron = (
        r"^(?:(?:oye|pero|mira)[, ]+)?"
        r"(?:te\s+)?(?:faltaron|faltan|olvidaste|falto|falta|"
        r"no\s+agregaste|no\s+incluiste)\s+"
        r"(?:las?|unos?|unas?|otros?|otras?)?\s*"
        r"(\d{1,6})\s+"
        r"(?:(?:piezas?|unidades?|estuches?|cajas?)\s+)?"
        r"(?:de\s+|para\s+)?(.+?)\s*[.!]?$"
    )
    match = re.fullmatch(patron, limpio)
    if match is None:
        return None
    cantidad = int(match.group(1))
    descripcion = match.group(2).strip()
    if not 1 <= cantidad <= 100000 or not 3 <= len(descripcion) <= 120:
        return "Dime cuántas piezas faltan y el producto, por ejemplo: FALTARON 15 DE PULSERA."
    if estado.get("cantidad_sugerida") is not None or estado.get("paso") in {"elegir", "cantidad"}:
        return (
            "Todavía estamos eligiendo un modelo de tu solicitud. "
            "Termina ese artículo primero y luego agregamos el faltante."
        )
    estado["cantidad_sugerida"] = cantidad
    estado["paso"] = "producto"
    respuesta = _buscar_producto(estado, descripcion, buscar, obtener_terminos)
    return f"Entendido: faltaron {cantidad} piezas de {descripcion}.\n" + respuesta


def _iniciar_busqueda(estado, texto, buscar, obtener_terminos):
    # No buscar palabras como COTIZAR o CARRITO en el catálogo.
    generico = re.sub(r"\s+", " ", _norm(texto).strip())
    if generico in {
        "cotizar", "cotizacion", "cotizaciones", "cotizame",
        "presupuesto", "carrito", "quiero cotizar",
        "quiero una cotizacion", "quisiera una cotizacion",
        "necesito una cotizacion", "quiero presupuesto",
        "necesito cotizar",
    }:
        estado["paso"] = "producto"
        return "¿Qué producto o referencia quieres agregar? Por ejemplo: 100 cajas para anillos."

    lotes = extraer_lotes(texto)
    if lotes:
        estado["pendientes"] = lotes[1:]
        estado["cantidad_sugerida"] = lotes[0]["cantidad"]
        return _buscar_producto(estado, lotes[0]["descripcion"], buscar, obtener_terminos)
    estado.pop("cantidad_sugerida", None)
    estado.pop("pendientes", None)
    # «Agrégame 200 cajas» no debe convertirse en «me 200 cajas».
    if re.match(r"^(?:agregame|agrégame|anademe|añademe)\\b", texto.strip(), re.I):
        return _buscar_producto(estado, texto, buscar, obtener_terminos)
    descripcion = re.sub(
        r"^(?:(?:quiero|quisiera|necesito)\s+)?"
        r"(?:cotizar|cotizacion|cotizaciones|cotizame|presupuesto|carrito|agregar|agrega|añadir|anadir)\s*",
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
        # Si una búsqueda falló dentro de un pedido de varios artículos,
        # conservar su cantidad y los artículos que todavía faltan.
        if "cantidad_sugerida" in estado:
            return _buscar_producto(estado, texto, buscar, obtener_terminos)
        return _iniciar_busqueda(estado, texto, buscar, obtener_terminos)
    if paso == "elegir":
        return _elegir(estado, texto, buscar, obtener_terminos)
    if paso == "cantidad":
        cantidad = validar_cantidad(texto)
        if cantidad is None:
            # Aceptar frases con UNA cantidad explícita: «ya te dije, 200».
            limpio_cantidad = _norm(texto).strip()
            numeros = re.findall(r"\b\d{1,6}\b", limpio_cantidad)
            expresiones = (
                "ya te", "ya me preguntaste", "son ", "quiero ",
                "necesito ", "ocupo ", "piezas", "unidades", "pero ",
                "serian ", "serían ", "en total",
            )
            if len(numeros) == 1 and any(t in limpio_cantidad for t in expresiones):
                cantidad = validar_cantidad(numeros[0])
        if cantidad is None:
            return (
                "Perdón, necesito confirmar la cantidad de este modelo. "
                "¿Cuántas piezas agrego? Por ejemplo: 200."
            )
        return _agregar_seleccion(estado, estado.pop("producto"), cantidad, buscar, obtener_terminos)
    if paso == "quitar_numero":
        seleccion = re.fullmatch(r"(?:el\s+)?(\d{1,2})", limpio)
        if not seleccion:
            return "¿Cuál número de la lista quieres quitar? Por ejemplo: 2."
        try:
            quitado = quitar_linea(estado["items"], int(seleccion.group(1)))
            estado["paso"] = "carrito"
            return f"Quité {quitado['nombre']}.\n\n" + _controles(estado["items"])
        except ValueError as error:
            return str(error) + "\nEscribe el número correcto."
    if paso == "carrito":
        faltante = _reponer_articulo_omitido(estado, texto, buscar, obtener_terminos)
        if faltante is not None:
            return faltante
        # Orden combinada: «quiero quitar el 3 y agregar otro».
        combinada = re.fullmatch(
            r"(?:quiero\s+)?(?:quitar|quitas|eliminar|borrar)\s+"
            r"(?:el\s+)?(\d{1,2})\s+y\s+"
            r"(?:(?:quiero\s+)?(?:agregar|agrega|anadir|añadir))\s*(.*)",
            limpio,
        )
        if combinada:
            try:
                retirado = quitar_linea(estado["items"], int(combinada.group(1)))
            except ValueError as error:
                return str(error) + "\n\n" + _controles(estado["items"])
            estado["paso"] = "producto"
            resto = combinada.group(2).strip()
            if resto in {"", "otro", "otra", "algo", "otro producto", "otra cosa"}:
                return (
                    f"Quité {retirado['nombre']}. "
                    "¿Qué nuevo producto o referencia quieres agregar?"
                )
            return (
                f"Quité {retirado['nombre']}.\n"
                + _iniciar_busqueda(estado, "agregar " + resto, buscar, obtener_terminos)
            )
        if limpio in {"agregar", "anadir", "añadir", "otro producto"}:
            estado["paso"] = "producto"
            return "¿Qué producto o referencia quieres agregar?"
        if limpio in {"quitar", "eliminar", "borrar", "quiero quitar"}:
            estado["paso"] = "quitar_numero"
            return "¿Cuál número de producto quieres quitar? Por ejemplo: 3."
        if re.match(
            r"^(?:quiero\s+)?(?:agregar|agrega|agregame|anadir|añadir|anademe)\s+",
            limpio
        ) or extraer_lotes(texto):
            return _iniciar_busqueda(estado, texto, buscar, obtener_terminos)
        quitar = re.fullmatch(r"(?:quiero\s+)?(?:quitar|quitas|eliminar|borrar)\s+(?:el\s+)?(\d{1,2})", limpio)
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
        return "No estoy seguro de qué quieres cambiar. Puedes decir por ejemplo: 'quita el 3 y agrega otro', 'cambia el 2 a 80', o 'agrega 200 cajas para aretes'.\n\n" + _controles(estado["items"])

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
        # El cliente puede corregir el borrador; se exigirá una nueva
        # revisión y CONFIRMAR antes de guardar sus datos.
        faltante = _reponer_articulo_omitido(estado, texto, buscar, obtener_terminos)
        if faltante is not None:
            return faltante
        if limpio in {"agregar", "anadir", "añadir"}:
            estado["paso"] = "producto"
            return "¿Qué artículo te faltó agregar?"
        if limpio in {"volver", "editar", "cambiar carrito"}:
            estado["paso"] = "carrito"
            return "Puedes editar el carrito.\n\n" + _controles(estado["items"])
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
