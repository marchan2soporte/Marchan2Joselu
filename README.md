# Marchan2 0.22 — JoseluIA

Copia de desarrollo **Marchan2Joselu**, creada el 26/10/2026 a partir de [Marchan2Pedro](https://github.com/marchan2soporte/Marchan2Pedro) en la base 0.21. Conserva el historial original; los cambios de esta copia se publican en Marchan2Joselu. Consulta [BASE_PEDRO.md](BASE_PEDRO.md) para el resumen de la revisión.

## Abrir
Extrae TODO el ZIP y conserva _internal junto a los dos ejecutables.
Cierra las versiones anteriores. Abre Marchan2_Administracion.exe para administrar y Marchan2_TPV.exe para vender. Las interfaces se abren en el navegador y comparten los datos del equipo.
Primer acceso: ADMIN / PIN 1234. Si ya habías cambiado el PIN, conserva el tuyo.
En Administración → Puntos de venta puedes configurar varios puestos y activar el que usa este TPV local. Instala primero la impresora de red en Windows para asignarla como cola de tickets o cocina. Si no hay cola asignada, «Ver cuenta» abre el diálogo de impresión de Windows. La IP guardada para el diagnóstico de red no es un destino de impresión. El puerto COM de balanza queda preparado para conectar un modelo con protocolo conocido.
En Plantillas de ticket, la vista previa usa el mismo formato que «Ver cuenta». Marca «Asignar este diseño al TPV activo al guardar» para aplicarlo al puesto en uso; una asignación directa del puesto prevalece sobre la plantilla predeterminada. En Puntos de venta → Impresoras puedes asignar colas de Windows al ticket de prueba y al informe Z, elegir impresión manual o automática del ticket y crear rutas de cocina por BARRA/COCINA y centro. Para una impresora Concod con controlador «Generic / Text Only», elige «Texto RAW» en el ticket, el Z y las rutas de cocina. El papel de 80 mm admite inicialmente 48 columnas; puedes ajustar columnas, líneas de avance y corte por destino. Prueba primero «Sin corte» y después «Corte parcial» solo si el equipo dispone de cortador ESC/POS compatible. El modo «Automático» intenta reconocer ese controlador. «Imprimir prueba» permite elegir RAW y envía una hoja real. Los trabajos fallidos aparecen para reintentarlos; comprueba la entrega con la impresora física.
Para probar dispositivos, guarda y activa el perfil. «Comprobar red» verifica la conexión TCP de la IP local y el puerto indicados sin imprimir; «Ver puertos COM» y «Leer balanza» prueban la lectura serie a la velocidad configurada. Los informes X/Z de jornada se abren desde Caja y jornada; usan el destino de impresión de Z del puesto. El antiguo resumen de prueba por fecha se conserva como compatibilidad interna, separado de los cierres nuevos.
Windows 10/11 de 64 bits; no requiere instalar Python ni conexión a Internet.

## Novedades 0.22 · venta y caja

- La cuenta ocupa toda la altura del área de venta. La calculadora permite operar, fijar la cantidad del próximo producto y cambiar unidades de una línea sin enviar ni pagos.
- Las acciones principales están a la derecha. Otros reúne cambiar mesa, cancelar ticket, imprimir, ingresos, gastos, retiradas, cuadre, informes X, cierre Z, historial, notas y último ticket.
- Administración → Botones permite arrastrar, ordenar con flechas o pasar acciones entre Derecha y Otros. Cada puesto conserva su distribución. Pagos y Otros permanecen accesibles en la zona principal.
- Administración → Jornadas y cierres permite consultar y reimprimir los informes guardados. Informes incorpora Movimientos de caja y Diario de cierres de caja.

## Calculadora, descuentos y peso

En Administración → Botones, selecciona el puesto y activa o desactiva «Mostrar calculadora». Al ocultarla la cuenta gana espacio; no borra descuentos ni pesos y no sustituye los permisos de usuario.

Selecciona una línea de la cuenta, calcula o teclea el valor y pulsa Dto % para un porcentaje o Dto €/ud para un importe **por unidad**. Quitar dto restaura el precio anterior al descuento. Reaplicar un descuento lo sustituye y no lo acumula sobre el precio ya rebajado. Las cuentas con cobros ya registrados no admiten estos cambios.

En Administración → Productos, activa «Vender por peso · precios por kilogramo». Todos los formatos de ese producto pasan a interpretarse como precios por KG. Al venderlo se pide el peso (0,250 = 250 g), con precisión de un gramo. Se registra una porción individual: el importe se redondea a céntimos antes de cobrar y los añadidos se cobran por porción. La calculadora puede cambiar el peso de una porción seleccionada mientras no se haya enviado a preparación. También funciona la venta al peso con la calculadora oculta, mediante el diálogo del producto.

Las unidades de los informes cuentan porciones, no kilogramos. Peso y descuento aparecen en la cuenta y el ticket; cocina recibe el peso sin precios. No hay descuento global de todo el ticket ni lectura de balanza conectada automáticamente a esta operación: el peso se introduce en el formulario o desde la calculadora.

## Apertura, arqueo y cierre operativo

Antes de vender se solicita el efectivo real de apertura, aunque sea 0 €. La jornada corresponde a la caja local compartida por estas dos aplicaciones; no hay sincronización entre cajas de distintos equipos.
Una jornada permanece abierta hasta cerrarla expresamente. Si queda abierta al cambiar de fecha, al entrar se avisa y se elige continuar el servicio nocturno o revisar/cerrar la jornada anterior.

El efectivo teórico es: fondo inicial + cobros en efectivo + propinas en efectivo + ingresos manuales − gastos − retiradas. El cambio entregado al cliente ya está descontado. Las tarjetas se registran aparte y las entradas/salidas manuales no se suman a las ventas. Para retirar propinas que estaban en el cajón, registra una retirada con su concepto.

El informe X consulta la jornada sin modificarla. Cuadre permite introducir el contado manualmente o calcularlo por monedas y billetes, y declarar opcionalmente el total del datáfono. Si existe una diferencia, se exige explicarla.
Cerrar jornada guarda un Z operativo con los importes, recuento, diferencia, movimientos y usuarios del cierre. No recalcula ese Z al consultarlo después. Las secciones adicionales se toman de la configuración del puesto al generar el informe; el cuadro mínimo de efectivo y diferencias siempre se conserva. No se puede cerrar mientras queden cuentas abiertas con productos o pagos. Las cuentas vacías se liberan al cerrar. Las operaciones repetidas de apertura, movimiento o cierre no se duplican.

Cancelar ticket conserva la cuenta y el motivo en el historial y libera su mesa. Solo admite cuentas abiertas sin cobros; las cuentas pagadas necesitan un procedimiento de devolución todavía pendiente. Si había preparación enviada, se exige permiso adicional y se indica que hay que avisar a cocina; no se retira una comanda ya impresa.

Se incorporan permisos independientes para apertura, consulta, movimientos, cierre y cancelación completa. Los administradores los tienen y el perfil Encargado inicial sin personalizar recibe los nuevos derechos. Los perfiles personalizados y Camarero no reciben derechos nuevos automáticamente.

Al actualizar, cierra las versiones anteriores antes de abrir 0.22. Los cobros históricos sin jornada no se asignan al nuevo fondo ni se vuelven a contar. Los datos y series existentes se conservan.

## Inicio
Ventas cerradas de hoy, semana (desde lunes), mes y año; cobros diferenciados; cuenta media; mesas ocupadas; cuentas pendientes; evolución frente al año anterior; cobros por método; ventas por categorías y centros; valoración del almacén manual actual, al inicio del mes y del año.
La venta se reconoce al cerrar la cuenta. Un pago parcial se reconoce en cobros al registrarlo; no cuenta como venta cerrada hasta finalizar la cuenta. Las cuentas divididas cerradas cuentan por separado.
No se calcula número de comensales ni margen comercial porque todavía no se registran los datos necesarios.

## Informes
Biblioteca por áreas con buscador. 30 informes disponibles con fechas y exportación CSV compatible con Excel. Las consultas de ventas recorren todo el histórico del intervalo, no solo las últimas 100 cuentas.
ALCANCE.md detalla el estado de cada informe. Los módulos pendientes no devuelven resultados ficticios.
Las agrupaciones por familia/categoría utilizan la clasificación actual de la carta. Los informes de usuario atribuyen las ventas a quien abrió la cuenta; los cobros conservan quien los registró.
El resumen de impuestos es orientativo, con IVA incluido y redondeo por tipo. No es una declaración ni un documento fiscal.

## Administración
Incluye los apartados identificados en las capturas, con diseño propio y estado visible.
Activos: empresa, series, configuración global, plantillas de ticket personalizables (formatos de papel, imágenes y opciones de contenido), productos, usuarios, creación de categorías/familias, centros/mesas, consultas de perfiles, impuestos, formas de pago, preparación y acceso al almacén manual. Consolidación de líneas, avisos de stock mínimo, motivos de cancelación, propinas, plantilla de comandas, resumen diario configurable y referencia interna de la serie de prueba actúan en el TPV. El resto de preferencias futuras queda guardado sin efecto operativo; consulta ALCANCE.md.
Los perfiles de usuario son editables. Los tipos de impuesto, métodos de pago y órdenes de preparación conservan los valores disponibles; todavía no hay un editor de esos valores personalizados.
Pendientes de implementación: locales independientes, otras plantillas, clientes, periodos de servicio, terminales en red, grupos mayores, menús, alérgenos, etiquetas, tarifas, promociones, descuentos y otras configuraciones señaladas en pantalla.

## Entradas de mercancía y almacén manual
Crea proveedores y artículos independientes del catálogo de venta. Registra recepciones por proveedor y referencia, salidas manuales o mermas. Admite cantidades positivas de hasta tres decimales y bloquea salidas superiores al saldo.
Cada movimiento registra un artículo; usa la misma referencia para las líneas de un albarán. Las operaciones quedan registradas y no hay aún editor de anulaciones de movimientos.
Las ventas del TPV NO descuentan este almacén automáticamente. Debes registrar todas las salidas manualmente. No hay aún recetas ni correspondencias entre artículos de almacén y formatos de venta.
Valoración: cantidad registrada multiplicada por el último coste de recepción disponible. No es coste medio ponderado ni margen de venta. Usa siempre el mismo criterio de impuestos al introducir costes; las compras no desglosan IVA en esta versión.

## TPV
Mantiene la venta táctil, selección de mesa o venta directa, acceso por usuario, formatos y añadidos, Preparar la comanda completa, Marchar la línea seleccionada, cambio de orden, mover cuenta y Pagos > Dividir cuenta por productos o importe.
La tarjeta se registra manualmente, no se conecta al datáfono. Preparar y Marchar envían a la pantalla de preparación local y, si hay rutas configuradas, también crean trabajos para las impresoras de cocina.

## Datos
Se mantienen en %LOCALAPPDATA%\Marchan2\marchan2.db. No se modifica Ágora. Una instalación nueva tiene carta y mesas de demostración. Las ventas simuladas de las capturas de prueba NO se incluyen en el ZIP.
Para copiar los datos, cierra ambas aplicaciones y copia toda la carpeta de datos. Cerrar una pestaña no cierra su proceso: usa el botón de encendido de la aplicación.

## Pendiente fiscal
TicketBAI está solicitado y pendiente; NO se ha implementado firma, envío, registro ni homologación. Tampoco está lista la facturación comercial ni los documentos fiscales. Los tickets siguen siendo de demostración/no fiscales.

## Validación
86 pruebas automatizadas y 4 pruebas de calculadora, más pruebas de ambos ejecutables: sesiones, permisos, datos compartidos, informes, proveedores, recepciones, valoración, ventas, pagos parciales y reinicio.
Fuentes: Python, SQLite y HTML/CSS/JS locales.
Ejecutar: python tpv.py / python admin.py
Pruebas: python -m unittest discover -s tests -v
Integración: python tests/check_dual_apps.py
Construir: python -m PyInstaller --noconfirm Marchan2_dual.spec
Ejecutables: python tests/check_dual_apps.py --frozen

## Repositorio y próximas actualizaciones
Repositorio oficial del proyecto: https://github.com/marchan2soporte/Marchan2Joselu.
Las actualizaciones de este trabajo se guardan aquí mediante commits, con su versión y cambios documentados. Las instrucciones persistentes están en AGENTS.md.
GitHub comprueba las pruebas en cada push. Los tags de versión (por ejemplo, v0.22) activan la construcción y publicación del ZIP de Windows. También puede construirse manualmente desde Actions > Windows release.
Los ejecutables se descargan desde Releases; el código fuente se mantiene en el repositorio. Conserva la carpeta _internal al extraer un paquete de Windows.
No se incluyen bases de datos, clientes, sesiones ni credenciales de los equipos de trabajo.

## Referencias de funcionamiento
Se han tomado como referencia conceptos de apertura, recuento y cierre propios de los TPV: [Arqueo Z de HIOPOS / ICGUniversity](https://newtraining.icguniversity.com/es/chapters/15/23/94/647/?sec=94) y [operaciones del manual oficial de Ágora](https://agorapos.com/manual/agora-retail/html/navigation.html). La interfaz y el código de esta ampliación son propios de Marchan2.
