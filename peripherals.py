"""Bounded diagnostics for optional LAN and serial devices."""
import ipaddress
import re
import socket

import pos_profiles


def printer_probe(store):
    opts = pos_profiles.active(store)['options']
    host = opts['network_printer'].strip()
    if not host:
        raise ValueError('Configura antes la dirección IP de la impresora.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError as error:
        raise ValueError('Introduce una dirección IP local para esta prueba.') from error
    if not (address.is_private or address.is_link_local):
        raise ValueError('La impresora debe estar en la red local.')
    port = opts['printer_port']
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError as error:
        raise ValueError(f'No se pudo abrir la conexión con {host}:{port}.') from error
    return {'ok': True, 'message': f'Conexión TCP abierta con {host}:{port}. No se ha enviado papel; la compatibilidad de impresión debe probarse desde Windows.'}


def serial_ports():
    try:
        from serial.tools import list_ports
    except ImportError:
        return {'ports': [], 'available': False}
    return {'ports': [{'name': item.device, 'description': item.description}
                       for item in list_ports.comports()], 'available': True}


def scale_probe(store):
    opts = pos_profiles.active(store)['options']
    port = opts['scale_port'].strip().upper()
    if not port:
        raise ValueError('Configura antes el puerto COM de la balanza.')
    try:
        import serial
    except ImportError as error:
        raise ValueError('Falta el controlador serie en esta instalación.') from error
    try:
        with serial.Serial(port=port, baudrate=opts['scale_baud'], timeout=2) as device:
            response = device.readline(128)
    except (serial.SerialException, OSError) as error:
        raise ValueError(f'No se pudo leer el puerto {port}.') from error
    text = response.decode('ascii', errors='replace').strip()
    if not text:
        raise ValueError(f'{port} se abrió, pero no envió datos. Revisa velocidad y protocolo de la balanza.')
    match = re.search(r'([+-]?\d+(?:[.,]\d+)?)\s*(kg|g)\b', text, re.IGNORECASE)
    return {'port': port, 'raw': text[:128],
            'weight_kg': round(float(match[1].replace(',', '.')) / (1000 if match[2].lower() == 'g' else 1), 3) if match else None,
            'message': 'Lectura recibida. El peso solo se interpreta si la balanza envía texto con unidad kg o g.'}
