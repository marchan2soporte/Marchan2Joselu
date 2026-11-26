# Estudio de competencia: Ágora, Numier y Qamarero

Fecha: 24/11/2026 · Versión de Marchan2 tras el estudio: 0.25

Se han revisado las webs públicas de producto de los tres TPV. Son páginas comerciales: describen lo que anuncian, no documentación técnica verificada. El manual de Ágora (agorapos.com/manual) no estaba disponible al consultarlo.

## Resumen por producto

**Ágora (Cegid)** — TPV local con gestión remota (My Ágora) y multi-local. Destaca en comandero (Ágora Comandas, Android e iOS), monitor de cocina (KDS) con colores y tiempos, reservas (Ágora Bookings: plano, turnos, señal por comensal, lista de espera, CRM con alergias y etiquetas VIP), delivery y take away propios, carta digital QR, Scan & Pay, autofactura por QR, auditoría de operaciones y cumplimiento VeriFactu.

**Numier** — TPV Windows con licencia local y sincronización en la nube. Destaca en el editor de planos de sala, comensales por mesa, múltiples tarifas y happy hour, invitaciones, descuentos y anulaciones controladas, cuentas aparcadas y cobro a crédito, caja ciega, PDA ilimitadas, monitor de cocina con tiempos medios, kiosko de autoventa, fichaje con pulseras NFC, inventario por app, escandallos, integraciones (Glovo, Uber Eats, Just Eat, CashDro, CashKeeper, Dojo, Redsys) y VeriFactu.

**Qamarero** — TPV en la nube centrado en pedir y pagar por QR desde la mesa (con aprobación del camarero, propina y factura desde el móvil). Divide cuentas por persona o producto, une y traslada cuentas, cartas con horarios por franja, combos y menús, comandero en el móvil del camarero, KDS, CRM y fidelización, tarjetas regalo, reservas, personal (turnos, control horario, vacaciones), escandallos, APPCC y VeriFactu/TicketBAI.

## Matriz de funciones

Leyenda: ✅ disponible · 🆕 añadido en 0.24 · ⏳ pendiente · 🚫 fuera de alcance local (requiere nube, terceros u homologación).

| Área | Función | Ágora | Numier | Qamarero | Marchan2 |
|---|---|:-:|:-:|:-:|:-:|
| Venta | Pantalla táctil, familias, categorías, búsqueda | ✔ | ✔ | ✔ | ✅ |
| Venta | Formatos y añadidos por producto | ✔ | ✔ | ✔ | ✅ |
| Venta | Productos favoritos y más vendidos | | ✔ | | 🆕 |
| Venta | Venta por peso con balanza | | ✔ | | ✅ (peso manual) |
| Venta | Descuento por línea | ✔ | ✔ | ✔ | ✅ |
| Venta | Descuento de ticket entero | ✔ | ✔ | ✔ | 🆕 |
| Venta | Invitaciones con motivo | | ✔ | | 🆕 |
| Venta | Tipo de servicio: mesa, barra, llevar, domicilio | ✔ | ✔ | ✔ | 🆕 |
| Venta | Múltiples tarifas / happy hour | | ✔ | ✔ | 🆕 0.25 |
| Venta | Menús y combos | ✔ | ✔ | ✔ | 🆕 0.25 |
| Venta | Promociones | ✔ | ✔ | ✔ | ⏳ |
| Sala | Mesas por centro de venta | ✔ | ✔ | ✔ | ✅ |
| Sala | Plano de sala editable | ✔ | ✔ | | 🆕 |
| Sala | Comensales por mesa | ✔ | ✔ | | 🆕 |
| Sala | Tiempo de ocupación de la mesa | ✔ | ✔ | | 🆕 |
| Sala | Mover cuenta de mesa | ✔ | ✔ | ✔ | ✅ |
| Sala | Unir cuentas | ✔ | | ✔ | 🆕 |
| Sala | Dividir cuenta por productos o importe | ✔ | ✔ | ✔ | ✅ |
| Cocina | Envío a cocina/barra, órdenes de preparación, marchar | ✔ | ✔ | ✔ | ✅ |
| Cocina | Monitor de cocina con tiempos | ✔ | ✔ | ✔ | 🆕 0.25 |
| Cobro | Efectivo, tarjeta, pagos parciales y mixtos | ✔ | ✔ | ✔ | ✅ |
| Cobro | Propinas | ✔ | | ✔ | ✅ |
| Cobro | Datáfono integrado | ✔ | ✔ | ✔ | 🚫 |
| Cobro | Pago QR desde el móvil del cliente | ✔ | ✔ | ✔ | 🚫 |
| Caja | Apertura, arqueo, X/Z, movimientos | ✔ | ✔ | ✔ | ✅ |
| Caja | Cajones inteligentes (CashDro, etc.) | ✔ | ✔ | ✔ | 🚫 |
| Clientes | Fichas con contacto y NIF | ✔ | ✔ | ✔ | 🆕 |
| Clientes | Alergias, notas y VIP | ✔ | | ✔ | 🆕 |
| Clientes | Historial de consumo | ✔ | ✔ | ✔ | 🆕 |
| Clientes | Fidelización y tarjetas regalo | | ✔ | ✔ | ⏳ |
| Carta | Alérgenos (14 UE) por producto | ✔ | ✔ | ✔ | 🆕 |
| Carta | Aviso de alergia del cliente en la cuenta | ✔ | | | 🆕 |
| Carta | Carta digital QR | ✔ | ✔ | ✔ | 🚫 |
| Personal | Usuarios, PIN y perfiles de permisos | ✔ | ✔ | ✔ | ✅ |
| Personal | Fichaje de entrada y salida | | ✔ | ✔ | 🆕 |
| Stock | Proveedores, entradas, mermas, valoración | ✔ | ✔ | ✔ | ✅ |
| Stock | Escandallos y descuento automático por venta | ✔ | ✔ | ✔ | 🆕 0.25 |
| Informes | Ventas, productos, usuarios, caja | ✔ | ✔ | ✔ | ✅ (44 informes) |
| Informes | Invitaciones, comensales, clientes, alérgenos, fichajes | ✔ | ✔ | ✔ | 🆕 |
| Pedidos | Tienda online, delivery, plataformas | ✔ | ✔ | ✔ | 🚫 |
| Reservas | Libro de reservas y widget web | ✔ | | ✔ | ⏳ |
| Comandero | App de comandas en móvil/PDA | ✔ | ✔ | ✔ | 🆕 0.25 (red local, móviles emparejados) |
| Fiscal | VeriFactu | ✔ | ✔ | ✔ | ⏳ registro encadenado en preparación (0.25), sin envío |
| Fiscal | TicketBAI | | | ✔ | ⏳ |
| Gestión | Backoffice en la nube y multi-local | ✔ | ✔ | ✔ | 🚫 |
| Equipo | Aplicación de escritorio Windows | ✔ | ✔ | | ✅ |
| Sistema | Copias de seguridad automáticas y restauración | ✔ | ✔ | ✔ | 🆕 0.25 |

## Qué se ha incorporado en 0.24

- **Comensales**: se piden al abrir una mesa nueva (se puede omitir) y se editan desde la cuenta.
- **Clientes**: vista Clientes en el TPV y en Administración. Las fichas incluyen teléfono, email, NIF, dirección, notas, alergias y VIP. Se asigna el cliente a la cuenta y se ven sus visitas y su gasto.
- **Aviso de alergias**: si el cliente asignado tiene alergias, la cuenta lo muestra y marca los productos con esos alérgenos.
- **Alérgenos y favoritos**: matriz de los 14 alérgenos por producto en Administración. Las teclas del TPV muestran sus siglas, y una pestaña reúne los favoritos (★).
- **Más vendidos**: pestaña automática con los productos más vendidos de los últimos 30 días.
- **Tipo de servicio**: mesa, barra, para llevar o domicilio (con dirección de entrega). Botones rápidos en Mesas.
- **Invitar**: una línea o toda la cuenta queda a 0 €, con motivo registrado e informe propio.
- **Descuento de ticket**: un porcentaje sobre todas las líneas, sin tocar las invitaciones. Se puede retirar.
- **Unir cuentas**: pasa los productos (y los comensales) de otra cuenta abierta sin pagos.
- **Fichaje**: entrada y salida desde la cabecera del TPV, con informe «Control horario».
- **Plano de sala**: editor por arrastre en Administración (forma y plazas por mesa) y vista Plano o Lista en el TPV, con comensales, tiempo y cliente de cada mesa.
- **Nuevos informes**: Invitaciones, Alérgenos por producto, Comensales por centro de venta, Cancelaciones por usuario, Descuentos por usuario y tipo, Ventas a cliente, Productos vendidos a cada cliente y Control horario.

## Qué se ha incorporado en 0.25

- **Tarifas y happy hour** por centro, días, franja horaria y categorías; aviso en el TPV cuando hay una tarifa horaria activa.
- **Menús**: un producto con apartados; el cliente elige un plato de cada uno, cocina recibe cada plato por su orden y la cuenta cobra el precio del menú.
- **Monitor de cocina** con cronómetro por comanda (verde, naranja a los 10 min, rojo a los 20), aviso sonoro, refresco automático e informe de tiempos.
- **Escandallos**: ingredientes por producto o formato; las ventas descuentan stock al cerrar la cuenta y hay informes de rentabilidad y márgenes.
- **Copias de seguridad**: diaria automática, al cerrar la jornada y manuales; carpeta configurable (disco externo o USB) y restauración con copia previa.
- **Comandero móvil** en la red local con emparejamiento por código, móviles revocables y diseño para el teléfono.
- **VeriFactu (preparación)**: registro de alta encadenado con huella SHA-256 (verificada con el ejemplo publicado por la AEAT) y comprobación de integridad. Sin envío ni homologación.
- Rediseño del cobro (dos columnas sin scroll), informes, tablas y directorio de administración.

## Pendiente, por prioridad recomendada

1. **VeriFactu**: el registro encadenado ya existe. Falta el envío a la AEAT con certificado, las anulaciones y subsanaciones, las facturas completas y rectificativas, la declaración responsable y el QR en el ticket. Obligatorio en España (según Numier, desde el 1/1/2026 para empresas y el 1/7/2026 para autónomos). TicketBAI en el País Vasco.
2. **Cifrado del comandero** (HTTPS en la red local) y app instalable en el móvil.
3. **Reservas**, fidelización y tarjetas regalo.
4. **Integraciones** (datáfono, cajones de efectivo, delivery, pago QR): dependen de acuerdos y SDK de terceros.

## Fuentes

- Ágora: [agorapos.com](https://agorapos.com/), [Software TPV restaurante](https://www.agorapos.com/software-tpv-restaurante/), [Monitor de cocina](https://www.agorapos.com/software-tpv-restaurante/monitor-de-cocina/), [Bookings](https://www.agorapos.com/software-tpv-restaurante/bookings/), [Ágora Comandas](https://www.agorapos.com/software-tpv-restaurante/agora-comandas/), [Delivery y take away](https://www.agorapos.com/software-tpv-restaurante/delivery-take-away/)
- Numier: [numier.com](https://www.numier.com/), [TPV hostelería](https://numier.com/software-tpv-hosteleria), [PDA](https://www.numier.com/numier-pda), [Cocina](https://www.numier.com/numier-cocina), [Carta digital](https://www.numier.com/numier-carta-digital), [Pedidos](https://www.numier.com/numier-pedidos), [Band](https://www.numier.com/numier-band), [Online](https://www.numier.com/numier-online), [Inventario](https://www.numier.com/numier-inventario), [VeriFactu](https://numier.com/verifactu/), [Integraciones](https://numier.com/integraciones/)
- Qamarero: [TPV hostelería](https://qamarero.com/tpv/), [Pedir y pagar QR](https://qamarero.com/pedir-y-pagar/), [Carta digital](https://www.qamarero.com/carta-digital/)
