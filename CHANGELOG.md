# Cambios de Marchan2

## 0.18
- La vista previa del editor de plantillas y «Ver cuenta» del TPV comparten ahora el mismo diseño de ticket, con los mismos campos y opciones. El TPV refresca la plantilla activa al abrir la cuenta.
- Administración muestra qué plantilla usa el TPV activo y permite asignar al puesto el diseño editado al guardarlo. La salida de texto RAW incorpora más campos y opciones de la plantilla; las imágenes siguen limitadas a la salida gráfica.

## 0.17
- Corrige la salida en blanco con controladores Windows «Generic / Text Only»: tickets, informe Z, comandas y prueba pueden enviarse como texto RAW. Se puede elegir el modo por destino o dejarlo en detección automática.
- Los trabajos conservan el modo elegido; la migración añade el ajuste sin reiniciar las colas ni borrar datos. La impresión física debe verificarse con el modelo instalado.

## 0.16
- Puntos de venta incorpora destinos de impresión para el ticket y el informe Z de prueba. El ticket puede imprimirse al pulsar el botón o automáticamente al completar el cobro, en una impresora instalada en Windows.
- Nuevas rutas de impresoras de cocina por tipo de preparación (BARRA, COCINA) y centros de venta. Preparar, Marchar y la preparación automática crean trabajos para las rutas correspondientes.
- Prueba de impresión, historial de trabajos, aviso de error y reintento manual. Una impresora desconectada no anula la venta ni la comanda. Proformas, facturas y otros documentos no emitidos por Marchan2 siguen pendientes.

## 0.15
- Informe Z operativo de prueba en el TPV, con secciones configurables por perfil y datos reales de ventas, cobros, cancelaciones, propinas y cuentas pendientes. Permite vista previa e impresión mediante Windows; no cierra la caja ni emite documentos fiscales.
- Diagnóstico desde el perfil activo: comprueba si se abre una conexión TCP a una IP local de impresora y enumera/lee puertos COM de balanzas que emitan peso en texto (kg o g). Incorpora velocidad serie configurable.
- El paquete Windows incluye el controlador serie. La impresión universal sigue usando el diálogo de Windows; el diagnóstico TCP no envía comandos de impresión.

## 0.14
- Nuevo apartado «Puntos de venta» con perfiles locales: crear, copiar, editar, activar y eliminar perfiles inactivos.
- El perfil activo controla cobros (también en el servidor), preparación automática, vista de búsqueda, última venta y plantilla de ticket de prueba. El saldo inicial de referencia aparece en el resumen de efectivo.
- Se pueden registrar la dirección o nombre de una impresora de red y un puerto COM para una futura conexión. La impresión actual se hace desde Windows; la lectura de balanza requiere el protocolo del modelo elegido.

## 0.13
- Editor de plantillas de ticket rediseñado con identidad visual propia, selector de anchuras de papel, vista previa en vivo y opciones de contenido.
- Cabecera y pie admiten imágenes PNG/JPEG pequeñas guardadas localmente. Las opciones de orden de productos, notas, precio unitario, IVA por línea, propinas, aviso de pendiente e identificación se aplican al recibo de prueba del TPV.
- Los QR fiscales, la asignación directa de impresoras y la emisión de facturas siguen pendientes.

## 0.12
- Configuración global: asignación de una plantilla de comanda existente; Preparación permite verla e imprimirla como documento interno de prueba.
- TPV: propinas opcionales con sugerencia por porcentaje o importe, registradas por separado de las ventas y visibles en el recibo de prueba.
- TPV: resumen diario de solo lectura que aplica los indicadores disponibles de cierre (centro, usuario, cobros, cancelaciones, familias, cuentas pendientes, efectivo y propinas). La impresión depende de la opción configurada; no ejecuta un cierre de caja.
- Las funciones de recargo, Scan & Pay con Redsys, pedido remoto en mesa, cierre automático y facturación web continúan pendientes de integración.

## 0.11
- TPV: aviso de stock mínimo, cancelación auditada con motivo configurable y referencia interna consecutiva de la serie asignada al cerrar una cuenta de prueba.
- Conexión inicial Administración/TPV: datos de Empresa en el ticket de prueba y consolidación de líneas controlada por Configuración global.
- Configuración global: formulario completo de preferencias guardadas para futuras funciones, con estado visible de lo que aún no afecta al TPV.
- Plantillas de ticket: editor con vista previa y aplicación de la plantilla predeterminada al detalle imprimible de las cuentas de prueba.
- Configuración global sustituye Locales y permite preparar la asignación de series; las demás opciones de la referencia indican su estado pendiente.
- Series: gestión local de series de documentos con búsqueda, copia, edición, eliminación y número siguiente previsto.
- Empresa: ficha editable de datos administrativos, ubicación y contacto, guardada localmente desde Administración.

## 0.3
- Nuevo inicio con ventas de hoy, semana, mes y año, cobros, comparativas y centros.
- Biblioteca de 69 apartados de informes; 28 disponibles con fechas y CSV.
- Administración por áreas, con estado explícito de las funciones pendientes.
- Almacén manual: proveedores, artículos, recepciones, salidas, mermas y valoración.
- TicketBAI solicitado y pendiente de implementación; los documentos siguen siendo de prueba.

## 0.2
- TPV y Administración separados, con datos compartidos y acceso por usuario/PIN.
- Venta táctil y selección de mesa o venta directa.
- Preparar comanda completa, Marchar línea seleccionada, cambiar orden y mover cuenta.
- Pagos parciales, mixtos y división por productos o importe dentro de Pagos.

## 0.1
- Primera versión local de TPV, catálogo y preparación.
