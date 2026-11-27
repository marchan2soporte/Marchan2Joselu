# Cambios de Marchan2

## 0.28
- Marchan2_Servidor.exe y server.cfg: servidor de red en segundo plano que arrancan solos el TPV y la Administración, instancia única, ventana de estado con «Detener servidor» y modo cliente para otros TPV.
- Emparejamiento del móvil persistente (cookie) y sesión guardada en el dispositivo; manifiesto web.
- Plano de mesas en el móvil.
- Cierre de jornada con cuentas abiertas: cobrarlas (lista de pendientes) o dejarlas para la siguiente jornada (en el Z).
- Pregunta de impresión al cobrar y salida a mesas.
- Monitores de cocina como app web independiente (/cocina) con disposición, volumen, sonido, listo por plato y recuperar; la vista de preparación sale del TPV.
- Tipos de preparación editables y monitores configurables en Administración.
- Productos agotados.
- 112 pruebas Python.

## 0.27
- ticket_print.py: maqueta común de documentos, salida de texto, ESC/POS (alineación, negrita, doble tamaño, logotipo PNG en trama, corte) y GDI con fuente monoespaciada ajustada al papel; imagen PNG de vista previa con el mismo código de dibujo.
- Plantillas: alineación de cabecera y pie, nombre y total grandes, separador y logotipo impreso; vista «Impresión exacta» y «Ver cuenta» con la imagen real.
- Comanda de cocina rediseñada.
- Detección del controlador de impresora con la API de Windows y caché (de ~5 s a 0,05 s).
- Cobro desde el móvil configurable (desactivado por defecto) y corrección de crypto.randomUUID en HTTP.
- PIN y código de emparejamiento con teclado propio en pantallas táctiles.
- Repetir ronda y «Pide la cuenta».
- 106 pruebas Python.

## 0.26
- web/tpv-mobile.js y web/mobile.css: interfaz propia de comandero para teléfono (mesas, carta y cuenta con controles táctiles, barra inferior, hojas inferiores, áreas seguras, vibración y refresco automático).
- Aviso «Listo para servir» en el móvil con vibración y sonido cuando cocina marca la comanda.
- Notas rápidas de preparación configurables en Administración y usadas en la nota de línea del TPV y del móvil.
- 101 pruebas Python.

## 0.25
- carta.py: tarifas y happy hour, menús con apartados, escandallos con descuento de stock al cobrar, tiempos de cocina y seis informes nuevos (44 disponibles).
- backup.py: copia diaria automática, al cerrar jornada y manual; carpeta y retención configurables; restauración con copia previa y comprobación de integridad.
- comandero.py: servicio opcional en la red local para móviles emparejados por código (token con huella SHA-256, bloqueo tras 5 fallos, revocación, sin cierre remoto) y diseño móvil.
- verifactu.py: registro de alta encadenado con huella SHA-256 según el algoritmo publicado por la AEAT, verificación de la cadena y URL de cotejo de pruebas. Sin envío ni homologación.
- Rediseño del cobro, tablas, informes y administración.
- 100 pruebas Python.

## 0.24
- Estudio de Ágora, Numier y Qamarero en ESTUDIO_COMPETENCIA.md, con matriz de funciones y pendientes.
- Nuevo módulo hospitality.py: comensales, clientes (CRM local con alergias y VIP), tipo de servicio (mesa, barra, llevar, domicilio), invitaciones, descuento de ticket, unir cuentas, alérgenos UE y favoritos por producto, fichaje y plano de mesas.
- TPV (web/tpv-plus.js): vista Clientes, plano de sala, chips de comensales/cliente/servicio en la cuenta, aviso de alergias, pestañas Favoritos y Más vendidos, siglas de alérgenos en las teclas, botón de fichaje y siete acciones nuevas configurables.
- Administración (web/admin-plus.js): Clientes, Alérgenos y favoritos, y editor de plano por arrastre.
- Ocho informes nuevos (38 disponibles) y tres permisos nuevos.
- La ventana de escritorio funciona con el ZIP descargado: se retira la marca de Internet de los archivos propios y los errores se guardan en desktop.log.
- 91 pruebas Python.

## 0.23
- TPV y Administración se ejecutan como aplicación de escritorio en ventana propia (pywebview + WebView2), maximizada. Cerrar la ventana o «Cerrar aplicación» detiene el servidor local. Opciones `--browser` y `--fullscreen`; si no hay WebView2 se usa el navegador.
- Pantalla completa con botón lateral o F11.
- Nueva capa de diseño `web/theme.css`: variables de color, modo claro/oscuro conmutable, productos y categorías con color estable por categoría, mesas ocupadas destacadas, total y Pagos más visibles, cabecera compacta y sin pie en la pantalla de venta.
- La apertura de jornada propone 0 € y el teclado reemplaza el valor al primer toque.
- Dos pruebas nuevas de la ventana de escritorio (88 en total).

## 0.22
- Calculadora habilitable por puesto, descuentos porcentuales o por unidad y porciones al peso en productos configurados por KG. Precios, pesos y cambios quedan registrados; los cobros usan céntimos enteros.
- Cuenta de venta hasta abajo, calculadora segura, multiplicador de unidades y acciones a la derecha.
- Otros con cancelación completa auditada, impresión, cambio de mesa, gastos, ingresos, retiradas, arqueo, X/Z, historial y última cuenta.
- Editor visual de botones por puesto, con arrastre y controles táctiles de orden y zona; conserva los permisos.
- Apertura obligatoria con fondo, jornada local persistente, aviso de jornada anterior, recuento por denominaciones y cierre con diferencia justificada.
- Informes X de consulta y Z inmutables, reimpresión e historial en Administración, más informes de movimientos y cierres.
- Las cuentas con pagos no pueden cancelarse y el cierre exige resolver cuentas abiertas. Los cobros anteriores a la migración conservan su histórico sin volver a contarse en caja.
- 86 pruebas Python, cuatro de calculadora y pruebas de ambos ejecutables con caja, permisos, layout y cobros.

## 0.21
- Perfiles de usuario editables en Administración, con 18 permisos asociados a las operaciones disponibles del TPV. Incluye Administrador, Encargado y Camarero; los usuarios existentes conservan su acceso al migrar.
- La asignación de perfil se guarda por usuario y el servidor comprueba permisos en cada petición del TPV, incluso cuando el perfil cambia durante una sesión abierta. Las acciones sin permiso se desactivan también en la interfaz.
- El listado de casi 500 permisos del archivo de referencia contiene módulos que Marchan2 aún no ofrece. Solo se muestran y aplican permisos para funciones disponibles; los demás siguen pendientes.

## 0.20
- Las comandas de una misma preparación se agrupan en una sola impresión por envío, con pedido, mesa, personal, secciones y productos sin precios. La vista del TPV sigue la misma estructura.
- El justificante de venta de prueba muestra columnas de productos e importes, resumen de IVA y cobros. La salida de texto para impresoras de 80 mm alinea los importes en 48 columnas.
- El documento sigue marcado como no fiscal. No se ha añadido el logotipo, QR ni contenido de Agora.

## 0.19
- Impresión RAW configurable por destino: ancho en caracteres, avance al final y corte ESC/POS completo o parcial opcional. Por defecto usa 48 columnas y cuatro líneas de avance, sin corte.
- La prueba de impresora incluye una regla de 48 columnas; el texto largo se ajusta al ancho elegido. Las comandas, tickets y Z conservan la configuración usada en cada trabajo. El corte requiere una impresora compatible y debe probarse físicamente.

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
