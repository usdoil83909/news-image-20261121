import os
import struct
import sys

import main

PAPER = bytes(main.PAPER)
SIZE = 120.0
X = 120.0
Y = 90.0


def ink_bands(text, font):
    sheet = main.Sheet()
    main.put_text(sheet, X, Y, text, SIZE, main.INK, font, weight=1)
    scale = SIZE / 21.0
    x0 = max(0, int((X - 4) * main.SS))
    x1 = min(sheet.w, int((X + main.text_width(text, SIZE, font) + 4) * main.SS))
    y0 = max(0, int((Y - 4) * main.SS))
    y1 = min(sheet.h, int((Y + 34 * scale + 4) * main.SS))
    stride = sheet.w * 3
    points = []
    for yy in range(y0, y1):
        base = yy * stride
        for xx in range(x0, x1):
            at = base + xx * 3
            if sheet.px[at:at + 3] != PAPER:
                points.append((xx, yy))
    assert points, 'no ink for %r' % text
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    top, bottom = min(ys), max(ys)
    height = bottom - top + 1
    widths = []
    for k in range(3):
        lo = top + height * k // 3
        hi = top + height * (k + 1) // 3
        band = [p[0] for p in points if lo <= p[1] < hi]
        widths.append(max(band) - min(band) + 1 if band else 0)
    first_row = [p[0] for p in points if p[1] == top]
    last_row = [p[0] for p in points if p[1] == bottom]
    edges = (max(first_row) - min(first_row) + 1,
             max(last_row) - min(last_row) + 1)
    return tuple(widths), max(xs) - min(xs) + 1, height, edges


def check_png(path):
    blob = open(path, 'rb').read()
    assert blob[:8] == b'\x89PNG\r\n\x1a\n'
    width, height = struct.unpack('>II', blob[16:24])
    assert (width, height) == (1024, 1024), (width, height)
    assert len(blob) <= 1024 * 1024, len(blob)
    return len(blob)


def main_probe():
    needed = ('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
              ' Percent$,.:?!/()*\'&+-·—')
    for symbol in needed:
        assert symbol in main.SANS, ('SANS missing', symbol)
        assert symbol in main.SERIF, ('SERIF missing', symbol)

    report = {}
    for font_name, font in (('SANS', main.SANS), ('SERIF', main.SERIF)):
        for text in ('L', 'P', '5'):
            widths, ink_width, height, edges = ink_bands(text, font)
            report[(font_name, text)] = widths
            print('%s %r: thirds=%s ink_width=%d height=%d top_row=%d bottom_row=%d'
                  % (font_name, text, widths, ink_width, height, edges[0], edges[1]))
            if text == '5':
                assert edges[0] >= 0.5 * ink_width, ('5 top bar', font_name, edges)
                if font_name == 'SANS':
                    assert edges[0] > 2 * edges[1], ('5 top bar', font_name, edges)

    for font_name in ('SANS', 'SERIF'):
        l = report[(font_name, 'L')]
        assert l[2] > 3 * l[0] and l[2] > l[1], ('L orientation', font_name, l)
        p = report[(font_name, 'P')]
        assert p[0] > 2 * p[2] and p[0] >= p[1], ('P orientation', font_name, p)

    for path in ('/tmp/n21a/entry.png', '/tmp/n21b/entry.png'):
        if os.path.exists(path):
            print('poster %s: bytes=%d' % (path, check_png(path)))

    line = ' '.join('%s%s=%d/%d/%d' % ((text, font_name[:2]) + report[(font_name, text)])
                    for text in ('L', 'P', '5') for font_name in ('SANS', 'SERIF'))
    print('probe=' + line)
    return 0


if __name__ == '__main__':
    sys.exit(main_probe())
