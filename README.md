# Marchan2 0.18 — JoseluIA

## Abrir
Extrae TODO el ZIP y conserva _internal junto a los dos ejecutables.
Cierra las versiones anteriores. Abre Marchan2_Administracion.exe para administrar y Marchan2_TPV.exe para vender. Las interfaces se abren en el navegador y comparten los datos del equipo.
Primer acceso: ADMIN / PIN 1234. Si ya habías cambiado el PIN, conserva el tuyo.
En Administración → Puntos de venta puedes configurar varios puestos y activar el que usa este TPV local. Instala primero la impresora de red en Windows para asignarla como cola de tickets o cocina. Si no hay cola asignada, «Ver cuenta» abre el diálogo de impresión de Windows. La IP guardada para el diagnóstico de red no es un destino de impresión. El puerto COM de balanza queda preparado para conectar un modelo con protocolo conocido.
En Plantillas de ticket, la vista previa usa el mismo formato que «Ver cuenta». Marca «Asignar este diseño al TPV activo al guardar» para aplicarlo al puesto en uso; una asignación directa del puesto prevalece sobre la plantilla predeterminada. En Puntos de venta → Impresoras puedes asignar colas de Windows al ticket de prueba y al informe Z, elegir impresión manual o automática del ticket y crear rutas de cocina por BARRA/COCINA y centro. Para una impresora Concod con controlador «Generic / Text Only», elige «Texto RAW» en el ticket, el Z y las rutas de cocina. El modo «Automático» intenta reconocer ese controlador. «Imprimir prueba» permite elegir RAW y envía una hoja real. Los trabajos fallidos aparecen para reintentarlos; comprueba la entrega con la impresora física.
Para probar dispositivos, guarda y activa el perfil. «Comprobar red» verifica la conexión TCP de la IP local y el puerto indicados sin imprimir; «Ver puertos COM» y «Leer balanza» prueban la lectura serie a la velocidad configurada. El informe Z de prueba se abre desde Mesas en el TPV y sus apartados se eligen en el perfil.
Windows 10/11 de 64 bits; no requiere instalar Python ni conexión a Internet.

## Inicio
Ventas cerradas de hoy, semana (desde lunes), mes y año; cobros diferenciados; cuenta media; mesas ocupadas; cuentas pendientes; evolución frente al año anterior; cobros por método; ventas por categorías y centros; valoración del almacén manual actual, al inicio del mes y del año.
La venta se reconoce al cerrar la cuenta. Un pago parcial se reconoce en cobros al registrarlo; no cuenta como venta cerrada hasta finalizar la cuenta. Las cuentas divididas cerradas cuentan por separado.
No se calcula número de comensales ni margen comercial porque todavía no se registran los datos necesarios.

## Informes
Biblioteca por áreas con buscador. 28 informes disponibles con fechas y exportación CSV compatible con Excel. Las consultas de ventas recorren todo el histórico del intervalo, no solo las últimas 100 cuentas.
ALCANCE.md detalla el estado de cada informe. Los módulos pendientes no devuelven resultados ficticios.
Las agrupaciones por familia/categoría utilizan la clasificación actual de la carta. Los informes de usuario atribuyen las ventas a quien abrió la cuenta; los cobros conservan quien los registró.
El resumen de impuestos es orientativo, con IVA incluido y redondeo por tipo. No es una declaración ni un documento fiscal.

## Administración
Incluye los apartados identificados en las capturas, con diseño propio y estado visible.
Activos: empresa, series, configuración global, plantillas de ticket personalizables (formatos de papel, imágenes y opciones de contenido), productos, usuarios, creación de categorías/familias, centros/mesas, consultas de perfiles, impuestos, formas de pago, preparación y acceso al almacén manual. Consolidación de líneas, avisos de stock mínimo, motivos de cancelación, propinas, plantilla de comandas, resumen diario configurable y referencia interna de la serie de prueba actúan en el TPV. El resto de preferencias futuras queda guardado sin efecto operativo; consulta ALCANCE.md.
Los perfiles, tipos de impuesto, métodos de pago y órdenes de preparación son los valores fijos de la versión anterior. Consultarlos no implica que ya exista un editor de valores personalizados.
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
59 pruebas automatizadas, más pruebas de ambos ejecutables: sesiones, permisos, datos compartidos, informes, proveedores, recepciones, valoración, ventas, pagos parciales y reinicio.
Fuentes: Python, SQLite y HTML/CSS/JS locales.
Ejecutar: python tpv.py / python admin.py
Pruebas: python -m unittest discover -s tests -v
Integración: python tests/check_dual_apps.py
Construir: python -m PyInstaller --noconfirm Marchan2_dual.spec
Ejecutables: python tests/check_dual_apps.py --frozen

## Repositorio y próximas actualizaciones
Repositorio oficial del proyecto: https://github.com/marchan2soporte/Marchan2Pedro.
Las actualizaciones de este trabajo se guardan aquí mediante commits, con su versión y cambios documentados. Las instrucciones persistentes están en AGENTS.md.
GitHub comprueba las pruebas en cada push. Los tags de versión (por ejemplo, v0.18) activan la construcción y publicación del ZIP de Windows. También puede construirse manualmente desde Actions > Windows release.
Los ejecutables se descargan desde Releases; el código fuente se mantiene en el repositorio. Conserva la carpeta _internal al extraer un paquete de Windows.
No se incluyen bases de datos, clientes, sesiones ni credenciales de los equipos de trabajo.
