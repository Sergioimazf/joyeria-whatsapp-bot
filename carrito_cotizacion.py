"""Funciones independientes para cotizaciones con varios productos.

No consulta APIs ni almacena datos: todo producto debe haberse validado antes
contra Dolibarr y el guardado final se realiza por separado en PostgreSQL.
"""

import re
import unicodedata

MAX_RENGLONES = 20
MAX_PIEZAS = 100000


def _normalizar(valor):
    valor = unicodedata.normalize("NFD", str(valor).casefold())
    return "".join(c for c in valor if unicodedata.category(c) != "Mn")


def validar_cantidad(texto):
    """Acepta '100', '100 piezas', '100 pz' sin tolerar números ambiguos."""
    limpio = _normalizar(texto).strip()
    encontrado = re.fullmatch(r"(\d{1,6})(?:\s*(?:piezas?|unidades?|pz|uds?))?", limpio)
    if not encontrado:
        return None
    cantidad = int(encontrado.group(1))
    return cantidad if 1 <= cantidad <= MAX_PIEZAS else None


def extraer_lotes(texto):
    """Detecta cantidades explícitas: '100 anillos y 50 collares'.

    No inventa productos, cantidades ni resuelve referencias; devuelve [] cuando
    el texto es ambiguo y la conversación debe solicitar una aclaración.
    """
    limpio = texto.strip()
    limpio = re.sub(
        r"^(?:(?:yo\s+)?(?:quiero|quisiera|necesito|me\s+gustaria)\s+)?"
        r"(?:cotizar|cotizacion\s+de|pedir|agregar|agrega|anadir|añadir)\s*",
        "", limpio, flags=re.I
    ).strip()
    limpio = re.sub(r"^(?:de|para|unas?|unos?|las?|los?)\s+", "", limpio, flags=re.I)
    segmentos = re.split(r"(?:\s+y\s+|\s+ademas\s+|[,;]\s*)(?=\d{1,6}\s)", limpio, flags=re.I)
    if not (1 <= len(segmentos) <= 10):
        return []
    resultado = []
    for segmento in segmentos:
        match = re.fullmatch(r"\s*(\d{1,6})\s+(.+?)\s*[.!]?\s*", segmento, flags=re.S)
        if not match:
            return []
        cantidad = int(match.group(1))
        descripcion = re.sub(r"^(?:de|para|unas?|unos?|las?|los?)\s+", "", match.group(2), flags=re.I).strip()
        if not (1 <= cantidad <= MAX_PIEZAS and 3 <= len(descripcion) <= 120):
            return []
        resultado.append({"descripcion": descripcion, "cantidad": cantidad})
    return resultado


def agregar_linea(items, producto, cantidad):
    """Agrega un producto confirmado, agrupando referencias repetidas."""
    if not isinstance(cantidad, int) or not 1 <= cantidad <= MAX_PIEZAS:
        raise ValueError("La cantidad debe estar entre 1 y 100000 piezas.")
    nombre = str(producto.get("nombre", "")).strip()[:140]
    referencia = str(producto.get("ref", "")).strip()[:70]
    if not nombre:
        raise ValueError("El producto no tiene nombre.")
    clave = referencia.casefold() if referencia else _normalizar(nombre)
    for item in items:
        clave_item = item["ref"].casefold() if item["ref"] else _normalizar(item["nombre"])
        if clave_item == clave:
            if item["cantidad"] + cantidad > MAX_PIEZAS:
                raise ValueError("La cantidad acumulada supera 100000 piezas.")
            item["cantidad"] += cantidad
            return items
    if len(items) >= MAX_RENGLONES:
        raise ValueError("El carrito admite máximo 20 productos distintos.")
    items.append({"nombre": nombre, "ref": referencia, "cantidad": cantidad})
    return items


def quitar_linea(items, numero):
    if not 1 <= numero <= len(items):
        raise ValueError("El número de producto no está en el carrito.")
    return items.pop(numero - 1)


def cambiar_cantidad(items, numero, cantidad):
    if not 1 <= numero <= len(items):
        raise ValueError("El número de producto no está en el carrito.")
    if not isinstance(cantidad, int) or not 1 <= cantidad <= MAX_PIEZAS:
        raise ValueError("La cantidad debe estar entre 1 y 100000 piezas.")
    items[numero - 1]["cantidad"] = cantidad
    return items[numero - 1]


def resumen_carrito(items):
    if not items:
        return "Tu carrito está vacío. Escribe AGREGAR para buscar un producto."
    lineas = ["🛒 CARRITO DE COTIZACIÓN"]
    for numero, item in enumerate(items, start=1):
        referencia = f" (Ref: {item['ref']})" if item["ref"] else ""
        lineas.append(f"{numero}. {item['nombre']}{referencia} — {item['cantidad']} piezas")
    lineas.append(f"Total: {sum(item['cantidad'] for item in items)} piezas en {len(items)} producto(s).")
    return "\n".join(lineas)
