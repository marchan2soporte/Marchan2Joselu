# Alcance funcional de Marchan2 0.18

Administración → Puntos de venta → Impresoras permite escoger entre las impresoras instaladas en Windows. El ticket de prueba puede imprimirse manualmente en una cola elegida o automáticamente al completar el cobro; el informe Z de prueba admite otra cola. Se pueden configurar rutas de impresión de cocina para BARRA, COCINA o ambos tipos, opcionalmente filtradas por centro de venta. Al preparar o marchar productos, se crean trabajos con las líneas recién enviadas. También funciona cuando la preparación automática está activada.

Una prueba envía una hoja real. Los trabajos se guardan con estado y error; se pueden reintentar si la impresora falla. La venta y la comanda no se deshacen por un fallo de impresión. La vista previa de Plantillas de ticket usa el mismo generador HTML que «Ver cuenta» del TPV. Se puede asignar una plantilla al puesto activo al guardarla. Las colas de texto RAW reciben un equivalente textual de los datos y opciones; las imágenes y el diseño gráfico requieren una impresora/controlador que los admita. La impresión directa admite texto RAW para colas «Generic / Text Only» y salida gráfica para otros controladores; el modo automático detecta el nombre del controlador. La recepción en la cola no garantiza que salga papel, por lo que hay que probarla físicamente. No usa un protocolo universal por IP ni emite documentos fiscales. La entrega física y el formato final dependen de la impresora instalada y deben verificarse con el equipo real. Proformas, facturas, albaranes, entradas y apertura de cajón todavía no se emiten desde Marchan2.

El TPV ofrece un informe Z operativo **de prueba** con vista previa e impresión mediante Windows. Las secciones se eligen en Administración → Puntos de venta para el perfil activo: ventas por usuario o centro, cobros por forma de pago, cancelaciones, propinas, cuentas pendientes, efectivo teórico y ventas por familia. Se alimenta de operaciones registradas; no realiza cierre contable, arqueo físico ni emisión fiscal.

En el perfil activo se puede comprobar una IP local y puerto TCP de impresora, sin enviar papel. Windows permite imprimir los tickets de prueba a cualquier impresora instalada, incluida una de red. El diagnóstico de balanza enumera puertos COM y lee una línea de texto con velocidad configurable; interpreta kg o g si la balanza lo transmite así. La incorporación del peso a artículos de venta requiere conocer el protocolo y el modelo de balanza, y aún no se realiza.

Administración → Puntos de venta permite mantener varios perfiles y activar uno para este TPV local. El perfil activo determina permisos de cobro, preparación automática de líneas nuevas, búsqueda inicial de productos, visualización de última venta y plantilla del ticket de prueba. El saldo inicial se usa como referencia en el resumen diario de efectivo, sin constituir un arqueo de caja. Los perfiles no representan terminales de red independientes.

Puede guardarse la IP de una impresora de red y el puerto COM de una balanza para usar los diagnósticos. La IP de diagnóstico no sustituye a una cola instalada en Windows. La impresión de documentos distintos del ticket y del informe Z de prueba, los visores externos, el uso del peso en la venta y las demás opciones avanzadas de la captura de referencia siguen pendientes.

Administración → Empresa permite guardar nombre fiscal, nombre comercial, CIF, dirección, población, provincia, código postal, contacto, teléfono, email y página web. Aceptar guarda la ficha local; Cancelar descarta la edición. Nombre comercial o fiscal, CIF y dirección aparecen en el detalle imprimible de prueba.

Administración → Series permite crear, buscar, copiar, editar y eliminar series de documentos con tipo, siguiente número y estado. La serie de «Fra. Simp.» asignada en Configuración global crea una referencia interna consecutiva en cuentas cobradas de prueba; no es numeración fiscal.

Administración → Configuración global sustituye la tarjeta Locales. Permite guardar asignaciones de series activas por tipo de documento para el punto de venta. La asignación de «Fra. Simp.» se usa solo como referencia interna en cuentas de prueba.

El formulario completo de Configuración global guarda además preferencias de stock, operativa de venta, comandas, propinas, recargo, pedidos, cierre y administración web. La consolidación de líneas, la plantilla de comandas y la sugerencia de propina sí se aplican en el TPV. Scan & Pay y pedido en mesa solo ofrecen el valor Desactivado hasta que existan esos módulos.

Conexión progresiva con TPV: Empresa aparece en el detalle imprimible de prueba (nombre comercial o fiscal, CIF y dirección); Consolidar líneas al vender ya controla si las nuevas líneas iguales se agrupan. La aplicación no emite facturas fiscales.

También están conectados al TPV: aviso cuando un artículo de almacén con mínimo configurado está por debajo de él; motivo obligatorio al cancelar una línea enviada a preparación cuando se activa esa opción; y referencia interna consecutiva de la serie «Fra. Simp.» al cobrar una cuenta completa. Las ventas siguen sin descontar existencias y la referencia interna no constituye factura ni numeración fiscal.

La plantilla de comandas seleccionada aporta cabecera y pie a la vista imprimible de Preparación. Al cobrar, el TPV sugiere una propina configurable que puede modificarse; se registra aparte de la venta y no altera el total de productos. El resumen diario del TPV muestra datos disponibles según las opciones de cierre: ventas por centro y usuario, cobros por usuario, cancelaciones por usuario, ventas por familia, cuentas pendientes, efectivo registrado y propinas por forma de pago. La opción «Imprimir diario de ventas» permite imprimir ese resumen de prueba. No se registra un cierre de caja ni se compara efectivo físico.

Siguen pendientes: recargo por servicio, datos de comensales e invitaciones, devoluciones, cierre automático y finalización automática de preparaciones, Scan & Pay/Redsys, pedido remoto en mesa y facturación legal o web. Las opciones guardadas para esas funciones no cambian el TPV. El límite de factura simplificada es una preferencia sin efecto fiscal hasta que exista un módulo de facturación validado.

Administración → Plantillas de ticket permite crear, copiar, editar y eliminar diseños de prueba; elegir 56 mm, variantes de 80 mm o A4; añadir texto e imágenes PNG/JPEG pequeñas a cabecera y pie; y configurar orden de productos, hora, usuario, impuestos orientativos, notas, ubicación, identificador interno, precio unitario y propinas. La plantilla predeterminada se aplica al detalle imprimible de las cuentas en TPV y Administración. La vista previa usa datos ficticios. La impresión directa a una cola de Windows usa una versión de texto del ticket; si no hay cola asignada, se abre el diálogo del sistema con el diseño visual. Las imágenes no se incluyen en la impresión directa de texto. No se generan facturas fiscales ni códigos QR fiscales.

28 informes disponibles de 69 apartados identificados. Los pendientes requieren más desarrollo; no son solo informes vacíos.

| Área | Informe | Estado |
|---|---|---|
| Visión del negocio | Análisis de ventas | Disponible |
| Visión del negocio | Análisis de compras | Disponible |
| Visión del negocio | Análisis de stocks | Disponible |
| Locales | Ventas por local | Pendiente |
| Locales | Comensales por local y periodo de servicio | Pendiente |
| Locales | Operaciones por local y periodo de servicio | Pendiente |
| Locales | Formatos de venta por local | Pendiente |
| Locales | Productos por local | Pendiente |
| Evolución | Evolución de ventas | Disponible |
| Evolución | Comparativa interanual | Disponible |
| Evolución | Resumen de impuestos | Disponible |
| Evolución | Invitaciones | Pendiente |
| Evolución | Reservas | Pendiente |
| Evolución | Documento 347 | Pendiente |
| Evolución | Estado de TicketBAI | Pendiente |
| Carta y rentabilidad | Grupos mayores | Pendiente |
| Carta y rentabilidad | Familias y productos | Disponible |
| Carta y rentabilidad | Categorías y productos | Disponible |
| Carta y rentabilidad | Productos en menús | Pendiente |
| Carta y rentabilidad | Márgenes por familias | Pendiente |
| Carta y rentabilidad | Márgenes por categorías | Pendiente |
| Carta y rentabilidad | Promociones y productos | Pendiente |
| Carta y rentabilidad | Alérgenos por producto | Pendiente |
| Carta y rentabilidad | Histórico de ventas | Disponible |
| Carta y rentabilidad | Rentabilidad de la carta | Pendiente |
| Carta y rentabilidad | Top 50 formatos | Disponible |
| Carta y rentabilidad | Top 50 productos | Disponible |
| Carta y rentabilidad | Ventas diarias | Disponible |
| Equipo | Rendimiento de usuarios | Disponible |
| Equipo | Usuarios por periodo de servicio | Pendiente |
| Equipo | Productos por usuario | Disponible |
| Equipo | Descuentos por usuario y producto | Pendiente |
| Equipo | Descuentos por usuario y tipo | Pendiente |
| Equipo | Cancelaciones por usuario | Pendiente |
| Espacios | Centros de venta | Disponible |
| Espacios | Ventas por ubicación | Disponible |
| Espacios | Productos por centro de venta | Disponible |
| Espacios | Comensales por centro de venta | Pendiente |
| Espacios | Operaciones por centro de venta | Disponible |
| Cobros y caja | Formas de pago | Disponible |
| Cobros y caja | Tarifas | Pendiente |
| Cobros y caja | Movimientos de caja | Pendiente |
| Cobros y caja | Cobros pendientes | Disponible |
| Cobros y caja | Propinas por formas de pago | Pendiente |
| Servicios | Productos por periodo de servicio | Pendiente |
| Servicios | Centros de venta por periodo de servicio | Pendiente |
| Servicios | Comensales por periodo de servicio | Pendiente |
| Servicios | Operaciones por periodo de servicio | Pendiente |
| Clientes | Ventas a cliente | Pendiente |
| Clientes | Facturas por cliente | Pendiente |
| Clientes | Impuestos por cliente | Pendiente |
| Clientes | Productos vendidos a cada cliente | Pendiente |
| Almacén | Entradas detalladas por proveedor | Disponible |
| Almacén | Compras por proveedor | Disponible |
| Almacén | Precios de compra | Disponible |
| Almacén | Compras y ventas por producto | Pendiente |
| Almacén | Stock por producto | Disponible |
| Almacén | Facturas de proveedor | Pendiente |
| Almacén | Histórico de compras | Disponible |
| Almacén | Movimientos por producto | Disponible |
| Almacén | Pagos pendientes | Pendiente |
| Almacén | Pedidos por recibir | Pendiente |
| Almacén | Valoración de mermas | Disponible |
| Cocina | Tiempos de preparación | Pendiente |
| Diarios | Diario de facturas | Pendiente |
| Diarios | Diario de albaranes | Pendiente |
| Diarios | Diario de pedidos | Pendiente |
| Diarios | Diario de cierres de caja | Pendiente |
| Diarios | Diario de ventas | Disponible |
