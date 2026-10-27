# Propuesta: carrito de cotización multiproducto

**Estado: versión experimental en rama separada. No desplegar en producción todavía.**

## Funciones preparadas

- Iniciar con COTIZAR o «Quiero cotizar 100 cajas para anillos y 50 para collares».
- Resolver cada descripción contra el catálogo existente de Dolibarr.
- Elegir el modelo exacto por número o referencia; no inventar referencias.
- AGREGAR más artículos, VER el resumen, QUITAR 2 y CAMBIAR 2 80.
- Máximo 20 artículos diferentes y 100 000 piezas por artículo.
- Un único folio para varios renglones, guardados en una transacción.
- Confirmación explícita antes de guardar el número de WhatsApp.
- Mostrar los renglones bajo su folio en el panel de ventas.
- No confirmar precios, stock ni crear pedidos reales.

## Requisitos previos al despliegue

1. Revisar las políticas comerciales con Carnevali.
2. Aprobar y aplicar el archivo migrations/001_cotizacion_multiproducto.sql
   en Neon y comprobar tabla y permisos del rol carnevali_rw.
3. Probar un guardado de varias líneas en base de pruebas y el panel de ventas.
4. Verificar que DATABASE_URL utiliza una cuenta no administradora.
5. Activar en Render CARRITO_MULTIPRODUCTO=1 solamente tras aprobar lo anterior.
6. Probar WhatsApp con dos productos, edición, eliminación y folio real.

Por defecto, CARRITO_MULTIPRODUCTO=0; el flujo actual sigue sin cambios.
La migración no se ha aplicado.

## Pruebas

python -m unittest discover -s tests -v

python -m compileall -q app.py carrito_cotizacion.py carrito_flujo.py

## Limitaciones

- La conversación sigue en memoria temporal de Render; los reinicios la borran.
- El parser necesita cantidad explícita para cada artículo en un mensaje.
- Búsquedas y sinónimos de Dolibarr requieren ejemplos de clientes reales.
- No contempla todavía tarifas, inventario reservado, pagos, Shopify ni avisos.
- Hay que validar reintentos, datos ambiguos, concurrencia y errores de red
  antes de utilizarlo con clientes reales.

## Información comercial pendiente

Pedido mínimo, precios autorizados, personalización, condiciones de envío,
cotizaciones válidas y situaciones que requieren un vendedor.
