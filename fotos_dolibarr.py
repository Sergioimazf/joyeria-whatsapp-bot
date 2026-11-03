"""Diagnóstico de fotografías de Dolibarr, solo lectura y solo modo pruebas.

No descarga imágenes, no muestra URLs internas y no altera el inventario.
"""
import re
from urllib.parse import quote

import requests

REF_SEGURA = re.compile(r"^[A-Za-z0-9._-]{2,70}$")
EXT_IMAGEN = re.compile(r"\.(?:jpe?g|png|webp)$", re.IGNORECASE)


def verificar_fotos(referencia, api_url, api_key, http=requests):
    """Devuelve una respuesta segura para WhatsApp, sin datos privados."""
    referencia = str(referencia).strip()
    if not REF_SEGURA.fullmatch(referencia):
        return "Escribe una referencia válida, por ejemplo: FOTO 3801.RD."
    if not api_key:
        return "La conexión con Dolibarr no está configurada."

    url = api_url.rstrip("/")
    headers = {"DOLAPIKEY": api_key}

    try:
        # Buscar por referencia EXACTA, jamás por aproximación visual.
        producto_respuesta = http.get(
            f"{url}/products/ref/{quote(referencia, safe='')}",
            headers=headers,
            timeout=8,
        )
        if producto_respuesta.status_code == 404:
            return f"No encontré la referencia {referencia} en Dolibarr."
        if producto_respuesta.status_code != 200:
            return (
                "No pude consultar la ficha del producto en Dolibarr. "
                "Revisa los permisos de lectura de productos."
            )
        producto = producto_respuesta.json()
        if not isinstance(producto, dict):
            return "Dolibarr devolvió una ficha inesperada."
        ref_real = str(producto.get("ref") or "")
        if ref_real.casefold() != referencia.casefold():
            return "No pude confirmar una coincidencia exacta de referencia."
        nombre = str(producto.get("label") or "Producto")[:100]
        identificador = producto.get("id") or producto.get("rowid")
        if not str(identificador).isdigit() or int(identificador) <= 0:
            return "El producto no tiene un ID válido para consultar sus fotos."

        archivos_respuesta = http.get(
            f"{url}/documents",
            headers=headers,
            params={"modulepart": "product", "id": int(identificador), "limit": 100},
            timeout=8,
        )
        # El 404 de /documents es ambiguo: puede significar que no hay
        # archivos, que la instancia no encuentra el directorio o que
        # el objeto no se resolvió. Repetir por referencia oficial ayuda
        # a diagnosticar sin inferir que no existen fotos.
        ruta = "id"
        if archivos_respuesta.status_code == 404:
            archivos_respuesta = http.get(
                f"{url}/documents",
                headers=headers,
                params={"modulepart": "product", "ref": ref_real, "limit": 100},
                timeout=8,
            )
            ruta = "referencia"
        if archivos_respuesta.status_code == 403:
            return (
                f"Encontré {nombre} (Ref: {ref_real}), pero Dolibarr "
                "rechazó consultar sus documentos (403). "
                "Necesitamos comprobar los permisos de la API."
            )
        if archivos_respuesta.status_code == 404:
            return (
                f"Encontré {nombre} (Ref: {ref_real}). "
                "La API de documentos respondió 404 tanto por ID como "
                "por referencia. Esto NO prueba que el producto no tenga "
                "fotos: podría deberse a su ubicación o configuración "
                "en Dolibarr. Revisa la pestaña Imágenes/Archivos "
                "adjuntos de ese producto."
            )
        if archivos_respuesta.status_code != 200:
            return (
                f"Encontré {nombre} (Ref: {ref_real}), "
                f"pero la API de documentos respondió "
                f"{archivos_respuesta.status_code} por {ruta}. "
                "No se ha confirmado el acceso a fotografías."
            )

        archivos = archivos_respuesta.json()
        if isinstance(archivos, dict):
            archivos = archivos.get("data")
        if not isinstance(archivos, list):
            return "Dolibarr devolvió un formato inesperado para documentos."

        imagenes = []
        for archivo in archivos:
            if not isinstance(archivo, dict) or archivo.get("type") == "dir":
                continue
            nombre_archivo = str(
                archivo.get("name") or archivo.get("relativename") or ""
            )
            if (
                EXT_IMAGEN.search(nombre_archivo)
                and "_preview" not in nombre_archivo.casefold()
                and not nombre_archivo.startswith(".")
            ):
                imagenes.append(nombre_archivo)

        if not imagenes:
            return (
                f"Encontré {nombre} (Ref: {ref_real}), pero ningún archivo "
                "JPG, PNG o WebP en los documentos visibles por la API."
            )
        return (
            f"✅ Dolibarr identifica {len(imagenes)} fotografía(s) para "
            f"{nombre} (Ref: {ref_real}).\n"
            "Esta es una verificación; todavía no se envían fotos al cliente. "
            "El siguiente paso es probar su descarga segura y el envío a WhatsApp."
        )
    except (requests.RequestException, ValueError, TypeError):
        return "No se pudo verificar la conexión a las fotos. Intenta más tarde."
