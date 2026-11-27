import base64
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import cash_register
import comandero
import hospitality
import printing
import ticket_print
import ticket_templates
from store import Store


def tiny_png(w=16, h=8):
    rows = b''.join(b'\x00' + bytes(0 if x < w // 2 else 255 for x in range(w)) for _ in range(h))
    chunk = lambda k, d: struct.pack('>I', len(d)) + k + d + struct.pack('>I', zlib.crc32(k + d) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
    return 'data:image/png;base64,' + base64.b64encode(png).decode()


class PrintDesignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name) / 'db.sqlite')
        ticket_templates.initialize(self.s)
        printing.initialize(self.s)

    def test_receipt_layout_alignment_sizes_and_widths(self):
        template = {'base': '80 mm · 42 caracteres', 'header': 'MI BAR', 'footer': 'GRACIAS', 'header_align': 'left',
                    'footer_align': 'right', 'separator': '=', 'header_large': 1, 'total_large': 1}
        doc = printing.receipt_doc(printing.SAMPLE_ORDER, {'tax_id': 'B1'}, template)
        self.assertEqual(doc['width'], 42)
        text = ticket_print.to_text(doc).splitlines()
        self.assertTrue(text[0].startswith('MI BAR'))
        self.assertEqual(text[-1], 'GRACIAS'.rjust(42))
        self.assertIn('=' * 42, text)
        total = next(line for line in text if line.startswith('TOTAL'))
        self.assertEqual(len(total), 21)
        self.assertTrue(total.endswith('33,50 EUR'))
        self.assertTrue(all(len(line) <= 42 for line in text))

    def test_escpos_commands_png_logo_and_cut(self):
        doc = printing.receipt_doc(printing.SAMPLE_ORDER, {}, {'header_image': tiny_png(), 'print_logo': 1})
        raw = ticket_print.escpos(doc, 48, 3, 'partial')
        self.assertTrue(raw.startswith(b'\x1b@\x1bt\x02'))
        self.assertIn(b'\x1dv0\x00', raw)
        self.assertIn(b'\x1ba\x01', raw)
        self.assertIn(b'\x1d!\x11', raw)
        self.assertTrue(raw.endswith(b'\n\n\n\x1d\x56\x01'))
        w, h, rows = ticket_print.decode_png(tiny_png())
        self.assertEqual((w, h, rows[0][0], rows[0][-1]), (16, 8, 0, 255))
        self.assertIsNone(ticket_print.decode_png('data:image/jpeg;base64,AAAA'))

    def test_jobs_store_designed_documents_and_plain_text_still_works(self):
        printing.save_document(self.s, {'profile_id': 1, 'kind': 'receipt', 'printer_name': 'Cola', 'copies': 1, 'backend': 'raw'})
        cash_register.mutate(self.s, 'cash_open', {'opening': '0', 'request_id': 'open-design'}, 1)
        oid = self.s.mutate('open', {'direct': True}, 1)['order_id']
        self.s.mutate('add', {'order_id': oid, 'format_id': 1}, 1)
        job = printing.enqueue_receipt(self.s, oid)['job_id']
        with self.s.db() as c:
            payload = c.execute('SELECT payload FROM print_jobs WHERE id=?', (job,)).fetchone()[0]
        self.assertTrue(ticket_print.is_doc(payload))
        self.assertEqual(printing._raw_bytes('Hola'), b'Hola\r\n\r\n\r\n\r\n\r\n')
        preview = printing.render_preview(self.s, order_id=oid)
        self.assertIn('JUSTIFICANTE DE VENTA', preview['text'])
        if sys.platform == 'win32':
            self.assertTrue(preview['image'].startswith('data:image/png;base64,'))

    def test_template_styles_saved_and_validated(self):
        base = dict(name='Diseño', base='80 mm', header='', footer='', show_time=True, show_user=True, show_tax=True, is_default=False)
        tid = ticket_templates.save(self.s, dict(base, header_align='right', separator='·', total_large=False))['id']
        row = next(t for t in ticket_templates.list_all(self.s) if t['id'] == tid)
        self.assertEqual((row['header_align'], row['separator'], row['total_large'], row['footer_align']), ('right', '·', 0, 'center'))
        with self.assertRaises(ValueError):
            ticket_templates.save(self.s, dict(base, name='Mal', header_align='diagonal'))

    def test_bill_request_and_mobile_payment_switch(self):
        cash_register.mutate(self.s, 'cash_open', {'opening': '0', 'request_id': 'open-bill-req'}, 1)
        oid = self.s.mutate('open', {'direct': True}, 1)['order_id']
        hospitality.mutate(self.s, 'bill_request', {'order_id': oid, 'requested': True}, 1, 'tpv')
        self.assertTrue(self.s.receipt(oid)['bill_requested_at'])
        hospitality.mutate(self.s, 'bill_request', {'order_id': oid, 'requested': False}, 1, 'tpv')
        self.assertIsNone(self.s.receipt(oid)['bill_requested_at'])
        comandero.initialize(self.s)
        self.assertFalse(comandero.allow_pay(self.s))
        comandero.configure(self.s, {'enabled': True, 'port': 8790, 'allow_pay': True})
        self.assertTrue(comandero.allow_pay(self.s))
        self.assertEqual(comandero.PAY_ACTIONS, {'pay', 'split_pay'})


if __name__ == '__main__':
    unittest.main()
