# Políticas operativas de Carnevali (fuente: respuestas de la propietaria)

Este documento recopila la información entregada para la automatización de WhatsApp.
No reemplaza la aprobación comercial de una vendedora. Los cambios deben confirmarse con la dirección.

## Contacto, sucursales y horarios

- **Valle:** Mississippi 415-2, entre Río Rosas y Gómez Morín, Plaza Santorini, San Pedro Garza García. Tel. 81 2710 7618 / 81 2710 7630. L–V 10:00–18:30; sábado 10:00–13:30.
- **Matriz:** Juan Méndez **644 Norte**, Centro Monterrey (el 664 en la imagen era inconsistente; **644 fue confirmado expresamente**). Tel. 81 8374 0873 / 81 8374 4167. L–V 10:00–18:30; sábado 10:00–13:00.
- **Plaza México:** Emilio Carranza 832, locales 11–12, Centro Monterrey. Tel. 81 8343 0265 / 81 1492 9332. L–V 10:00–19:00; sábado 10:30–18:00.
- Página web utilizada por el bot: https://carnevaliestuches.com
- **PENDIENTE:** número oficial de *WhatsApp de ventas*. No asumir que alguno de los teléfonos de sucursal tiene WhatsApp ni que realiza recepción automática.

## Servicio y productos

- Preguntas frecuentes: ubicaciones, mayoreo, cobertura de envíos, catálogo, tiempos de entrega.
- Especialidad: suministros para el gremio joyero, estuches, cajas y exhibidores.
- La propietaria confirma que todos los productos están en Dolibarr y que nombres, referencias, colores y medidas se actualizan allí.
- Las fotografías están archivadas; todavía no se ha validado la recuperación automática desde Dolibarr ni la correspondencia del catálogo de Waffle.
- El bot debe ofrecer nombre, referencia y detalles disponibles, sin deducir medidas o materiales no publicados.
- Si no hay producto exacto, atención humana; las vendedoras pueden sugerir alternativas.

## Precios, ventas y cotizaciones

- Los precios publicados pueden consultarse en el catálogo en línea. Precios finales de cotización y costos de impresión **solo vendedores**.
- Menudeo desde 1 pieza; mayoreo según volumen. En grandes compras puede ofrecerse **hasta 5%** sujeto a aprobación comercial; no aplicar de forma automática.
- Compra mínima en línea: **$800 MXN**.
- Dolibarr muestra existencias, pero **no siempre son en tiempo real**. Confirmar antes de prometer disponibilidad.
- Si el cliente solicita más cantidad que la existente, ventas puede evaluar pedido especial según modelo, volumen y plazo.
- Solicitud multiproducto: artículos con referencias/modelos exactos; agregar, quitar y cambiar cantidades/modelos antes del pago.
- Se permiten varias cotizaciones por cliente. **PENDIENTE**: el prototipo actual guarda solo un borrador activo por WhatsApp, no múltiples borradores paralelos.
- Cotización aprobada por ventas: vigencia de **una semana**.
- Ventas revisa y envía cotización al cliente por correo o WhatsApp; el carrito automático no es una cotización aprobada.
- Datos necesarios: referencias, cantidades, y para envíos foráneos datos para cotizar el flete. No solicitar dirección completa ni RFC en un chat automático sin un proceso seguro.

## Pagos y pedidos

- Métodos aceptados: efectivo, transferencias, PayPal, cheque, tarjetas de crédito y débito.
- Para impresión de logo hay anticipo; monto y condiciones a confirmar con ventas.
- Venta por WhatsApp suele comenzar en tienda en línea; ventas proporciona fotografías de ángulos según dudas.
- Un vendedor debe supervisar la confirmación de pedidos. **PENDIENTE**: definir si se enviará a Shopify para pagar y cómo verificar pagos.
- Facturas: datos de Constancia de Situación Fiscal por canal seguro autorizado, no pedirla en texto de chat.

## Envíos, entregas y posventa

- Envíos a todo México y posibilidad internacional con costos mayores.
- Flete según peso, volumen y destino, confirmado por ventas.
- Plazo habitual de entrega **3–6 días hábiles**, sujeto a existencia, destino y tipo de pedido. No garantizar fecha.
- Paquetería a elección del cliente dentro de las opciones disponibles.
- Recogida en sucursal permitida, coordinada con ventas.
- La guía se envía al cliente para consultar estatus. **PENDIENTE**: bot todavía no consulta estado en Shopify/paqueterías.
- Envíos foráneos necesitan atención humana rápida; problemas de mercancía dañada, incompleta o incorrecta se revisan y, según corresponda, se reponen o cambian.

## Personalización

- Serigrafía y hot stamping según materiales.
- Cantidad mínima **100 piezas por tamaño**.
- Necesita logotipo vectorizado.
- Producción aproximada **2–3 semanas** según temporada.
- Técnica, costo y anticipo autorizados por vendedora.

## Cambios y devoluciones

- Cambios de diseño antes de facturar; devolución por mercancía dañada.
- Productos equivocados: cambio por el correcto.
- Cancelación sin anticipo se tramita sin problema con ventas; cancelaciones con anticipo requieren revisión.
- Pocas quejas reportadas; cualquier incidencia se deriva a personal.

## Automatización y hoja de ruta

- Objetivo de la propietaria: atención desde «Hola» hasta cierre de venta y seguimiento, con preparación física/envío humano.
- **Ya conectado:** WhatsApp Cloud API para mensajes de texto, lectura de catálogo Dolibarr y guardado de solicitudes confirmadas en Neon.
- **En desarrollo:** respuestas oficiales y ficha individual, integración de IA para clasificar preguntas (código opcional; **apagado** por defecto), fotos por referencia.
- **Pendiente de integración/decisión:** WhatsApp oficial de ventas, fotos correctas, múltiples cotizaciones simultáneas, revisión/aprobación comercial, Shopify, pagos verificados, guías y seguimiento, notificaciones a ventas y pruebas de carga/errores.
- Nunca generar ni aprobar precios, fletes, descuentos, pedidos o pagos sin fuente verificable y autorización del negocio.

## API de OpenAI (opcional, no habilitada)

- El módulo `openai_intenciones.py` prepara llamadas a la **Responses API** solo para **clasificar** preguntas, no para inventar respuestas libres.
- Solo si Render tiene `IA_CARNEVALI_MODO=pruebas`, `OPENAI_API_KEY` y el remitente escribió `PROBAR CARRITO` se usará IA cuando no hay carrito activo y las reglas no identifican la intención.
- Modelo configurable `OPENAI_MODEL` (valor por defecto `gpt-4.1-mini`). API de OpenAI se factura separadamente de ChatGPT.
- Guardar clave **solo** en variables privadas de Render; no mandarla por WhatsApp, GitHub ni este chat.
- No activar públicamente hasta probar funcionamiento, costos, permisos, tratamiento de datos y límites de uso.
