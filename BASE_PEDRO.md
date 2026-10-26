# Base de Marchan2Joselu

- Origen: https://github.com/marchan2soporte/Marchan2Pedro
- Revisión de origen: `6ee495955d2b5c5d2b9f9d0694dabb9a3a634140`
- Versión de aplicación recibida: **0.21**.
- Copia independiente preparada el **26/10/2026**.
- Destino de los cambios de Joselu: https://github.com/marchan2soporte/Marchan2Joselu.

## Avances revisados

La base conserva dos aplicaciones locales, TPV y Administración, un servidor Python y SQLite compartido, más la interfaz HTML/CSS/JavaScript.

Además de las funciones de la versión 0.3, incorpora:

- Empresa, series de documentos internos y configuración global.
- Plantillas de ticket con imágenes, papel, vista previa y asignación al puesto activo.
- Perfiles locales de puntos de venta y opciones de cobro y preparación.
- Perfiles de usuario editables con permisos comprobados en el servidor.
- Rutas de impresoras de cocina, cola de trabajos, errores y reintentos.
- Impresión de Windows en modo gráfico o RAW, con ancho, avance y corte opcionales.
- Propinas, motivos de cancelación y resúmenes diarios/Z de prueba.
- Diagnóstico de impresoras de red y lectura de balanzas serie compatibles.

## Alcance que sigue pendiente

La copia no convierte el prototipo en un sistema fiscal: TicketBAI y facturación comercial siguen pendientes. El informe Z es una vista de prueba; no ejecuta un cierre de caja. El almacén sigue siendo manual y no se descuenta con las ventas. Otras funciones futuras se describen en ALCANCE.md.

## Preparación de esta copia

Se conservan el historial y las etiquetas originales. Solo se adaptan el destino de publicación, los metadatos y las notas de procedencia. Las publicaciones automáticas nuevas usan el prefijo `joselu-v` para distinguirlas de las etiquetas heredadas. No se modifican los comportamientos del TPV ni los datos de ningún equipo.

La copia inicial no recrea las antiguas páginas de Releases ni sus archivos adjuntos; conserva las referencias Git. Las siguientes compilaciones se generan en el nuevo repositorio.

## Puntos detectados para futuras modificaciones

- El servidor anuncia todavía `0.16` en `/api/access`, mientras la base y el paquete indican `0.21`.
- Algunas notas del README siguen describiendo perfiles fijos, aunque el código más reciente permite perfiles de usuario editables.
- Los dos ejecutables utilizan por defecto `%LOCALAPPDATA%\Marchan2`. Para probar esta copia junto a otra versión, iniciar con `--data` en una carpeta independiente.
- La impresión física depende de las colas, controladores y equipos instalados. Las pruebas automatizadas usan sustitutos y datos temporales, sin imprimir.
