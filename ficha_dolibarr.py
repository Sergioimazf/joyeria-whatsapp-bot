"""Consulta de ficha por referencia EXACTA en la API actual de Dolibarr.

No crea pedidos, no muestra claves y no confirma precios ni disponibilidad.
"""
import re
from html import unescape
from urllib.parse import quote

import requests


REFERENCIA = re.compile(r"^[A-Za-z0-9._-]{2,70}$")


def _limpiar_html(texto):
    texto = re.sub(r"<[^>]*>", " ", str(texto or ""))
    return re.sub(r"\s+", " ", unescape(texto)).strip()


def consultar_ficha(referencia, api_url, api_key, http=requests):
    ref = str(referencia).strip()
    if not REFERENCIA.fullmatch(ref):
        return "Escribe una referencia válida, por ejemplo: FICHA 3801.RD."
    if not api_key:
        return "No está configurada la conexión con el catálogo Dolibarr."
    try:
        r = http.get(
            f"{api_url.rstrip('/')}/products/ref/{quote(ref, safe='')}",
            headers={"DOLAPIKEY": api_key},
            timeout=8,
        )
        if r.status_code == 404:
            return f"No encontré la referencia {ref} en Dolibarr. Puedes consultar a ventas."
        if r.status_code != 200:
            return "No pude consultar la ficha en Dolibarr. Intenta más tarde o contacta a ventas."
        producto = r.json()
        if not isinstance(producto, dict):
            return "Dolibarr devolvió un formato inesperado de producto."
        ref_real = str(producto.get("ref") or "").strip()
        if ref_real.casefold() != ref.casefold():
            return "No pude verificar la referencia exacta. No mostraré otro producto por error."

        nombre = _limpiar_html(producto.get("label") or producto.get("ref"))[:140]
        if not nombre:
            nombre = ref_real
        lineas = [f"📦 {nombre}", f"Referencia: {ref_real}"]
        descripcion = _limpiar_html(producto.get("description"))
        if descripcion:
            lineas.append(f"Descripción: {descripcion[:600]}")
        # Los nombres de campo y las unidades pueden variar entre versiones
        # de Dolibarr. No inventar dimensiones/material si faltan o carecen de
        # unidades explícitas. Mostrar únicamente metadatos descriptivos.
        nota = _limpiar_html(producto.get("note_public"))
        if nota and nota != descripcion:
            lineas.append(f"Detalles: {nota[:300]}")
        # Un valor registrado no es una promesa de disponibilidad real.
        stock = producto.get("stock_reel")
        if stock is not None and not isinstance(stock, bool):
            try:
                stock_numero = float(stock)
                if 0 <= stock_numero <= 100000000:
                    stock_texto = str(int(stock_numero)) if stock_numero.is_integer() else str(stock_numero)
                    lineas.append(f"Existencias registradas: {stock_texto} (por confirmar con ventas)")
            except (TypeError, ValueError, OverflowError):
                pass

        lineas.append(
            "Para fotos, medidas o materiales que no aparezcan en esta ficha, "
            "consulta al equipo de ventas. Precios de tienda en línea: "
            "https://carnevaliestuches.com. "
            "Precios especiales, existencias y cotización final sujetos a revisión."
        )
        return "\n".join(lineas)
    except (requests.RequestException, ValueError, TypeError):
        return "No pude consultar la ficha en Dolibarr. Intenta más tarde o contacta a ventas."
