#!/usr/bin/env python3
"""Orientation self-checks and contact proof for every text draw path."""

import sys

from PIL import Image, ImageDraw

sys.path.insert(0, '/root/makefun/news21-entry')
import main


SIZE = 120.0
TRACKING = 0.0
SQUEEZE = 0.92
START = 120.0
TOP = 140.0


def drawers():
    width_x = main.text_width('X', SIZE, main.SANS, TRACKING, SQUEEZE)
    width_dot = main.text_width('.', SIZE, main.SANS, TRACKING, SQUEEZE)
    total = width_x + width_dot

    def put_text(sheet, font):
        main.put_text(sheet, START, TOP, 'X.', SIZE, main.INK, font,
                      weight=2, tracking=TRACKING, squeeze=SQUEEZE)

    def put_centered(sheet, font):
        main.put_centered(sheet, START + total / 2.0, TOP, 'X.', SIZE,
                          main.INK, font, weight=2, tracking=TRACKING,
                          squeeze=SQUEEZE)

    def caps(sheet, font):
        main.caps(sheet, START, TOP, 'X.', SIZE, main.INK, font,
                  weight=2, tracking=TRACKING, squeeze=SQUEEZE)

    def put_wrapped(sheet, font):
        main.put_wrapped(sheet, START, TOP, 'X.', SIZE, total + 100,
                         main.INK, font, weight=2, tracking=TRACKING,
                         squeeze=SQUEEZE)

    return [
        ('put_text', put_text),
        ('put_centered', put_centered),
        ('caps', caps),
        ('put_wrapped', put_wrapped),
    ]


def orientation_check(name, drawer, font_name, font):
    sheet = main.Sheet()
    drawer(sheet, font)
    probe = '/tmp/_orient_%s_%s.png' % (name, font_name)
    main.write_png(probe, main.SIDE, main.SIDE, sheet.reduce())
    image = Image.open(probe).convert('RGB')
    pix = image.load()

    width_x = main.text_width('X', SIZE, font, TRACKING, SQUEEZE)
    width_dot = main.text_width('.', SIZE, font, TRACKING, SQUEEZE)
    x0 = int(START)
    x1 = int(START + width_x)
    x2 = int(START + width_x + width_dot)
    top = int(TOP)
    bottom = int(TOP + 13.0 * (SIZE / 21.0))

    def ink(left, right):
        return sum(1 for y in range(top, bottom)
                   for x in range(left, right)
                   if pix[x, y][0] < 140)

    left_ink = ink(x0, x1)
    right_ink = ink(x1, x2)
    ok = left_ink > 30 and left_ink > 6 * max(1, right_ink)
    verdict = 'OK' if ok else 'MIRRORED'
    print('SELFCHECK %-12s %-5s X.[left=%5d right=%5d] %s'
          % (name, font_name, left_ink, right_ink, verdict))
    assert ok, '%s/%s failed orientation check (%d vs %d)' % (
        name, font_name, left_ink, right_ink)
    return ok


def isolated_image(draw):
    sheet = main.Sheet()
    draw(sheet)
    image = Image.frombytes('RGB', (main.SIDE, main.SIDE), bytes(sheet.reduce()))
    grey = image.convert('L')
    paper = int(0.299 * main.PAPER[0] + 0.587 * main.PAPER[1]
                + 0.114 * main.PAPER[2])
    mask = grey.point(lambda v: 255 if abs(v - paper) > 12 else 0)
    box = mask.getbbox()
    if box is None:
        return image
    pad = 12
    box = (max(0, box[0] - pad), max(0, box[1] - pad),
           min(main.SIDE, box[2] + pad), min(main.SIDE, box[3] + pad))
    return image.crop(box)


def contact_items():
    def masthead(s):
        main.put_centered(s, 512, 100, main.DATE_TEXT, 54, main.INK,
                          main.SERIF, weight=4, tracking=0.4, squeeze=0.92)

    def subline(s):
        line = '  ·  '.join(main.TOP3)
        main.put_centered(s, 512, 100, line, 26, main.GREY, main.SERIF,
                          weight=2, tracking=0.2, squeeze=0.95, slant=0.13)

    def regions(s):
        cursor = 40.0
        for name, count, tint in main.REGIONS:
            label = '%s %d' % (main.SHORT_REGION.get(name, name), count)
            size = main.fit_size(label, 118, 20, 12,
                                 main.SANS, 0.25, 0.78)
            s.rect(cursor * main.SS, 90 * main.SS,
                   128 * main.SS, 44 * main.SS, tint)
            main.put_centered(s, cursor + 64, 99, label, size, main.WHITE,
                              main.SANS, weight=3, tracking=0.25, squeeze=0.78)
            cursor += 128

    def also_heading(s):
        main.put_text(s, 40, 100, 'ALSO ON ' + main.DATE_TEXT, 34, main.RED,
                      main.SANS, weight=4, tracking=0.4, squeeze=0.9)

    def datecheck(s):
        line = ("Left out as Friday 20 November's news: "
                + '; '.join(main.LEFT_OUT) + '.')
        main.put_text(s, 40, 100, line, 20, main.INK, main.SANS,
                      weight=2, tracking=0.1, squeeze=0.95)
        main.put_text(s, 40, 140, 'Every story here happened, or was first '
                      'reported, on %s.' % main.DATE_TEXT,
                      20, main.RED, main.SANS, weight=2,
                      tracking=0.15, squeeze=0.95)

    def footer(s):
        note = ('SOURCES: AP, AFP, Reuters, BBC, Al Jazeera, Jiji Press, '
                'RBC-Ukraine, POLITICO, Rio Times and the agencies credited '
                'on every story.')
        main.put_centered(s, 512, 100, note, 22, main.GREY, main.SANS,
                          weight=2, tracking=0.25, squeeze=0.9)

    return [
        ('masthead', masthead),
        ('subline', subline),
        ('region strip', regions),
        ('ALSO heading', also_heading),
        ('DATE CHECK text', datecheck),
        ('footer SOURCES', footer),
    ]


def make_contact():
    pieces = [(label, isolated_image(draw)) for label, draw in contact_items()]
    width = max(1300, max(img.width for _, img in pieces) + 120)
    height = 24 + sum(img.height + 70 for _, img in pieces)
    contact = Image.new('RGB', (width, height), (252, 250, 245))
    painter = ImageDraw.Draw(contact)
    y = 12
    for label, img in pieces:
        painter.text((24, y), label + '  (fixed draw path)', fill=(20, 20, 20))
        y += 24
        contact.paste(img, (48, y))
        painter.line((16, y + img.height + 8, width - 16, y + img.height + 8),
                     fill=(178, 168, 150))
        y += img.height + 46
    contact.save('/tmp/contact.png')
    print('CONTACT /tmp/contact.png %dx%d' % contact.size)
    return contact.size


def main_entry():
    verdicts = 0
    for font_name, font in (('SANS', main.SANS), ('SERIF', main.SERIF)):
        for name, drawer in drawers():
            verdicts += orientation_check(name, drawer, font_name, font)
    size = make_contact()
    print('SELFCHECK VERDICTS: %d/%d PASS (per function, per font)'
          % (verdicts, verdicts))
    print('CONTACT DIMENSIONS: %dx%d' % size)


if __name__ == '__main__':
    main_entry()
