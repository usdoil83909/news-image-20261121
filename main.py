#!/usr/bin/env python3
"""A deterministic, stdlib-only broadsheet drawn one pixel at a time."""

import hashlib
import math
import os
import struct
import zlib

SIDE = 1024
SS = 3
PIX = SIDE * SS
OUT = os.path.join(os.environ.get('MAKEFUN_OUTPUT_DIR', '/output'), 'entry.png')

PAPER = (244, 239, 227)
INK = (27, 27, 27)
RED = (192, 57, 43)
OXBLOOD = (112, 32, 40)
BLUE = (31, 78, 156)
AMBER = (217, 142, 43)
DARK = (30, 36, 44)
GREY = (94, 88, 80)
RULE = (178, 168, 150)
WHITE = (246, 243, 237)
PALE = (250, 246, 238)
MUTED = (151, 145, 134)


class Sheet:
    __slots__ = ('w', 'h', 'px')

    def __init__(self):
        self.w = PIX
        self.h = PIX
        self.px = bytearray(bytes(PAPER) * (PIX * PIX))

    def rect(self, x, y, w, h, col):
        x, y, w, h = int(x), int(y), int(w), int(h)
        if w <= 0 or h <= 0:
            return
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        run = bytes(col) * (x1 - x0)
        stride = self.w * 3
        for yy in range(y0, y1):
            off = yy * stride + x0 * 3
            self.px[off:off + len(run)] = run

    def dot(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            off = (y * self.w + x) * 3
            self.px[off] = col[0]
            self.px[off + 1] = col[1]
            self.px[off + 2] = col[2]

    def seg(self, ax, ay, bx, by, col, weight=2):
        ax, ay, bx, by = int(round(ax)), int(round(ay)), int(round(bx)), int(round(by))
        weight = max(1, int(weight))
        limit = (weight / 2.0 + 0.35) ** 2
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        pad = weight // 2 + 2
        for yy in range(max(0, min(ay, by) - pad), min(self.h - 1, max(ay, by) + pad) + 1):
            for xx in range(max(0, min(ax, bx) - pad), min(self.w - 1, max(ax, bx) + pad) + 1):
                if length2 == 0:
                    d2 = (xx - ax) ** 2 + (yy - ay) ** 2
                else:
                    t = ((xx - ax) * dx + (yy - ay) * dy) / length2
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                    ex = xx - (ax + t * dx)
                    ey = yy - (ay + t * dy)
                    d2 = ex * ex + ey * ey
                if d2 <= limit:
                    self.dot(xx, yy, col)

    def outline(self, pts, col, weight=2, closed=False):
        for i in range(len(pts) - 1):
            self.seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], col, weight)
        if closed and len(pts) > 2:
            self.seg(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1], col, weight)

    def area(self, pts, col):
        if len(pts) < 3:
            return
        top = max(0, int(math.floor(min(p[1] for p in pts))))
        bot = min(self.h - 1, int(math.ceil(max(p[1] for p in pts))))
        count = len(pts)
        for yy in range(top, bot + 1):
            crossings = []
            for i in range(count):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % count]
                if ay == by:
                    continue
                if ay > by:
                    ax, ay, bx, by = bx, by, ax, ay
                if ay <= yy < by:
                    crossings.append(ax + (bx - ax) * (yy - ay) / (by - ay))
            crossings.sort()
            for i in range(0, len(crossings) - 1, 2):
                left = max(0, int(math.ceil(crossings[i])))
                right = min(self.w, int(math.ceil(crossings[i + 1])))
                if right > left:
                    self.rect(left, yy, right - left, 1, col)

    def disc(self, cx, cy, radius, col, ring=False, weight=2):
        cx, cy = int(round(cx)), int(round(cy))
        outer = radius * radius
        inner = (radius - weight) ** 2
        for yy in range(max(0, int(cy - radius - 1)), min(self.h - 1, int(cy + radius + 1)) + 1):
            for xx in range(max(0, int(cx - radius - 1)), min(self.w - 1, int(cx + radius + 1)) + 1):
                dist = (xx - cx) ** 2 + (yy - cy) ** 2
                if (ring and inner <= dist <= outer) or (not ring and dist <= outer):
                    self.dot(xx, yy, col)

    def reduce(self):
        result = bytearray(SIDE * SIDE * 3)
        stride = self.w * 3
        for y in range(SIDE):
            base = y * SS * stride
            for x in range(SIDE):
                r = g = b = 0
                for dy in range(SS):
                    row = base + dy * stride + x * SS * 3
                    for dx in range(SS):
                        at = row + dx * 3
                        r += self.px[at]
                        g += self.px[at + 1]
                        b += self.px[at + 2]
                out = (y * SIDE + x) * 3
                result[out] = (r + 4) // 9
                result[out + 1] = (g + 4) // 9
                result[out + 2] = (b + 4) // 9
        return result


def write_png(path, width, height, rgb):
    def piece(tag, body):
        return (struct.pack('>I', len(body)) + tag + body
                + struct.pack('>I', zlib.crc32(tag + body) & 0xffffffff))

    scan = bytearray()
    stride = width * 3
    for y in range(height):
        scan.append(0)
        scan.extend(rgb[y * stride:(y + 1) * stride])
    blob = (b'\x89PNG\r\n\x1a\n'
            + piece(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + piece(b'IDAT', zlib.compress(bytes(scan), 9))
            + piece(b'IEND', b''))
    with open(path, 'wb') as handle:
        handle.write(blob)
    return blob


# JHF stroke outlines, re-keyed into a compact per-glyph record:
# "symbol|left,right|x,y;x,y/x,y;x,y".  Order is digits, capitals,
# lowercase, marks rather than the source table's ASCII sequence.
FONT_RAW = r"""
0|-10,10|-1,-12;-4,-11;-6,-8;-8,-3;-9,1;-9,5;-8,9;-6,12;-4,13;-1,14;1,14;4,13;6,12;8,9;9,5;9,1;8,-3;6,-8;4,-11;1,-12;-1,-12
1|-10,10|-4,-8;-2,-9;1,-12;1,14
2|-10,10|-6,-6;-6,-7;-5,-9;-4,-11;-2,-12;2,-12;4,-11;5,-9;6,-7;6,-5;5,-3;3,0;-7,10;7,10
3|-10,10|-5,-12;6,-12;0,-2;3,-2;5,-1;6,0;7,3;7,5;6,8;4,10;1,11;-2,11;-5,10;-6,9;-7,7
4|-10,10|3,14;3,-12/-8,5;8,5
5|-10,10|5,-12;-5,-12;-5,-1;-5,-2;-2,-3;1,-3;4,-2;6,0;7,3;7,5;6,8;4,10;1,11;-2,11;-5,10;-6,9;-7,7
6|-10,10|6,-9;5,-11;2,-12;0,-12;-3,-11;-5,-8;-6,-3;-6,-2;-5,1;-3,3;0,4;1,4;4,3;6,1;7,-2;7,-3;6,-6;4,-8;1,-9;0,-9;-3,-8;-5,-6;-6,-3
7|-10,10|7,-12;-3,14
8|-10,10|-2,-12;-5,-11;-6,-9;-6,-7;-5,-5;-4,-4;-1,-3;3,-2;5,-1;6,1;7,3;7,6;6,8;5,9;2,10;-2,10;-5,9;-6,8;-7,6;-7,3;-6,1;-5,-1;-3,-2;1,-3;4,-4;5,-5;6,-7;6,-9;5,-11;-2,-12
9|-10,10|6,-5;5,-8;3,-10;0,-11;-1,-11;-4,-10;-6,-8;-7,-5;-7,-4;-6,-1;-4,1;-1,2;0,2;3,1;5,-1;6,-4;6,-5;5,-10;3,-12;0,-13
A|-10,10|-8,14;-8,-12/-8,-12;8,-12/-5,2;5,2
B|-11,11|-9,14;-9,-12/-9,14;2,14;5,13;6,12;7,10;7,8;6,6;5,5;2,4;-9,4/2,4;5,3;6,2;7,0;7,-3;6,-5;5,-6;2,-7;-9,-7
C|-11,11|8,7;7,9;5,11;3,12;0,13;-3,13;-6,12;-8,10;-9,8;-10,5;-10,-1;-9,-4;-8,-6;-6,-8;-3,-9;0,-9;3,-8;5,-6;7,-4;8,-1
D|-11,11|-9,14;-9,-12/-9,14;0,14;3,13;5,11;6,9;7,6;7,0;6,-3;5,-5;3,-7;0,-8;-9,-8
E|-10,10|-8,14;-8,-12/-8,14;6,14/-8,2;0,2/-8,-12;6,-12
F|-10,10|-8,14;-8,-12/-8,14;6,14/-8,2;0,2
G|-11,11|8,7;7,9;5,11;3,12;0,13;-3,13;-6,12;-8,10;-9,8;-10,5;-10,-1;-9,-4;-8,-6;-6,-8;-3,-9;0,-9;3,-8;5,-6;7,-4;8,-1;8,3/3,3;8,3
H|-11,11|-9,14;-9,-12/7,14;7,-12/-9,2;7,2
I|-5,5|0,14;0,-12
J|-9,9|4,14;4,-7;3,-10;1,-12;-1,-12;-3,-10;-4,-8
K|-11,11|-9,14;-9,-12/7,14;-9,-2/-2,5;7,-12
L|-10,10|-8,14;-8,-12/-8,-12;6,-12
M|-12,12|-10,14;-10,-12/0,14;0,-12/10,14;10,-12/-10,14;0,-12;10,14
N|-11,11|-9,14;-9,-12/7,14;7,-12/-9,14;7,-12
O|-11,11|-2,14;-5,13;-7,11;-8,9;-9,6;-9,0;-8,-3;-7,-5;-5,-7;-2,-8;2,-8;5,-7;7,-5;8,-3;9,0;9,6;8,9;7,11;5,13;2,14;-2,14
P|-11,11|-9,14;-9,-12/-9,14;2,14;5,13;6,12;7,10;7,7;6,5;5,4;2,3;-9,3
Q|-11,11|-2,14;-5,13;-7,11;-8,9;-9,6;-9,0;-8,-3;-7,-5;-5,-7;-2,-8;2,-8;5,-7;7,-5;8,-3;9,0;9,6;8,9;7,11;5,13;2,14;-2,14/1,-5;7,-11
R|-11,11|-9,14;-9,-12/-9,14;2,14;5,13;6,12;7,10;7,8;6,6;5,5;2,4;-9,4/0,4;7,-12
S|-10,10|7,9;5,11;2,12;-2,12;-5,11;-7,9;-7,7;-6,5;-5,4;-3,3;3,1;5,0;6,-1;7,-3;7,-6;5,-8;2,-9;-2,-9;-5,-8;-7,-6
T|-10,10|0,14;0,-12/-9,14;9,14
U|-11,11|-9,14;-9,-3;-8,-6;-6,-8;-3,-9;0,-9;3,-8;5,-6;6,-3;7,0;7,14
V|-10,10|-10,14;0,-12/10,14;0,-12
W|-13,13|-12,14;-8,-12/-4,14;-8,-12/-4,14;4,-12/12,14;4,-12
X|-10,10|-9,14;7,-12/7,14;-9,-12
Y|-10,10|-10,14;0,0;10,14/0,0;0,-12
Z|-10,10|7,14;-9,-12/-9,14;7,14/-9,-12;7,-12
a|-8,8|6,9;6,-3/-2,9;1,9;3,8;4,7;5,5;6,2;6,-1;5,-4;4,-5;3,-6;1,-7;-2,-7;-4,-6;-5,-5;-6,-3;-6,-1;-5,2;-4,4;-2,5;1,5;3,4;4,3;6,0
b|-8,8|-8,14;-8,-12/-8,2;-6,4;-4,5;-1,6;2,6;4,5;6,3;7,0;7,-2;6,-5;4,-7;2,-8;-1,-8;-4,-7;-6,-5;-8,-2
c|-8,8|6,4;5,6;3,8;1,9;-2,9;-4,8;-6,6;-7,3;-7,1;-6,-2;-4,-4;-2,-5;1,-5;3,-4;5,-2;6,0
d|-8,8|6,14;6,-12/6,2;4,4;2,5;-1,6;-4,6;-6,5;-7,3;-8,0;-8,-2;-7,-5;-6,-7;-4,-8;-1,-8;2,-7;4,-5;6,-2
e|-8,8|-7,1;6,1;6,3;5,5;4,6;2,7;-1,7;-3,6;-5,4;-6,1;-6,-1;-5,-4;-3,-6;-1,-7;2,-7;4,-6;6,-4
f|-6,6|5,14;5,-11;4,-13;2,-14;0,-14;-2,-13;-3,-11/-3,5;4,5
g|-8,8|6,9;6,-7;5,-10;4,-11;2,-12;-1,-12;-3,-11/6,2;4,4;2,5;-1,6;-4,6;-6,5;-7,3;-8,0;-8,-2;-7,-5;-6,-7;-4,-8;-1,-8;2,-7;4,-5;6,-2
h|-8,8|-6,14;-6,-12/-6,2;-4,4;-2,5;1,6;3,6;5,5;6,2;6,-12
i|-4,4|-1,14;-2,13;-1,12;0,13;-1,14/-1,9;-1,-12
j|-5,5|0,14;-1,13;0,12;1,13;0,14/0,9;0,-11;-1,-13;-3,-14;-5,-14
k|-8,8|-6,14;-6,-12/5,9;-6,-2/-1,4;6,-12
l|-4,4|0,14;0,-12
m|-12,12|-11,9;-11,-12/-11,2;-9,4;-7,5;-4,6;-2,6;0,5;1,2;1,-12/1,2;3,4;5,5;8,6;10,6;12,5;13,2;13,-12
n|-8,8|-6,9;-6,-12/-6,2;-4,4;-2,5;1,6;3,6;5,5;6,2;6,-12
o|-8,8|-1,9;-4,8;-6,6;-7,3;-7,1;-6,-2;-4,-4;-1,-5;1,-5;4,-4;6,-2;7,1;7,3;6,6;4,8;1,9;-1,9
p|-8,8|-8,9;-8,-14/-8,2;-6,4;-4,5;-1,6;2,6;4,5;6,3;7,0;7,-2;6,-5;4,-7;2,-8;-1,-8;-4,-7;-6,-5;-8,-2
q|-8,8|6,9;6,-14/6,2;4,4;2,5;-1,6;-4,6;-6,5;-7,3;-8,0;-8,-2;-7,-5;-6,-7;-4,-8;-1,-8;2,-7;4,-5;6,-2
r|-7,7|-3,9;-3,-12/-3,1;-2,3;0,5;2,6;4,6
s|-8,8|6,6;4,8;1,9;-2,9;-5,8;-6,6;-6,4;-5,2;-4,1;-2,0;2,-1;4,-2;5,-3;6,-5;6,-7;4,-9;1,-10;-2,-10;-5,-9;-6,-7
t|-6,6|0,14;0,-11;1,-13;3,-14;5,-14/-4,5;3,5
u|-8,8|-6,9;-6,-5;-5,-7;-3,-8;0,-8;2,-7;4,-5/6,9;6,-12
v|-8,8|-8,9;0,-12/8,9;0,-12
w|-11,11|-10,9;-6,-12/-2,9;-6,-12/-2,9;2,-12/10,9;2,-12
x|-8,8|-6,9;6,-12/6,9;-6,-12
y|-8,8|-8,9;0,-12/0,9;-2,-2;-5,-10;-9,-14
z|-8,8|6,9;-6,-12/-6,9;6,9/-6,-12;6,-12
!|-5,5|0,-12;0,2/0,7;-1,8;0,9;1,8;0,7
"|-8,8|-4,-12;-4,-5/4,-12;4,-5
$|-10,10|-2,-16;-2,13/2,-16;2,13/7,-9;5,-11;2,-12;-2,-12;-5,-11;-7,-9;-7,-7;-6,-5;-5,-4;-3,-3;3,-1;5,0;6,1;7,3;7,6;5,8;2,9;-2,9;-5,8;-7,6
%|-16,16|-9,-11;-8,-12;-6,-12;-4,-11;-3,-9;-3,-7;-4,-5;-6,-4;-14,4;-16,5;-17,7;-17,9;-16,11;-14,12;-12,12;-10,11;-9,9/-4,-12;14,12/5,2;3,3;2,5;2,7;4,10;6,12;8,12;10,11;11,9;11,6;10,4;8,2;6,1;4,1;2,2
&|-15,15|-3,-3;-5,-5;-7,-6;-9,-6;-11,-5;-13,-3;-14,-1;-14,1;-13,3;-12,4;-10,5;-4,7;-2,8;-1,9;0,11;0,13;-1,15;-3,16;-5,17;-7,17;-9,16;-11,15/-13,-12;-13,-10;-12,-8;-11,-7;-10,-6;-6,-4;-4,-3;-2,-2;0,0;2,3;3,5;3,7;2,9;0,11;-1,12;-3,13;-5,13;-7,12;-9,10;-10,8;-10,6;-9,4;-7,2;-5,0;-1,-2;1,-3;3,-4;5,-5;7,-6;9,-7;11,-9;12,-11;12,-13
'|-5,5|0,-12;-1,-11;0,-10;1,-11;0,-12
(|-7,7|4,-16;2,-14;0,-11;-2,-7;-3,-2;-3,2;-2,7;0,11;2,14;4,16
)|-7,7|-4,-16;-2,-14;0,-11;2,-7;3,-2;3,2;2,7;0,11;-2,14;-4,16
*|-10,10|0,-12;0,6/-5,-9;5,-3/-5,-3;5,-9
+|-13,13|0,-12;0,9/-9,-1;9,-1
,|-5,5|1,5;0,6;-1,5;0,4;1,5;1,7;0,9;-1,10
-|-13,13|-9,-1;9,-1
.|-5,5|0,4;-1,5;0,6;1,5;0,4
/|-11,11|-9,16;9,-16
:|-5,5|0,-4;-1,-3;0,-2;1,-3;0,-4/0,4;-1,5;0,6;1,5;0,4
;|-5,5|0,-4;-1,-3;0,-2;1,-3;0,-4/1,5;0,6;-1,5;0,4;1,5;1,7;0,9;-1,10
<|-13,13|8,-11;-8,-1;8,9
=|-13,13|-9,-4;9,-4/-9,2;9,2
>|-13,13|-8,-11;8,-1;-8,9
?|-10,10|-6,-6;-6,-7;-5,-9;-4,-11;-2,-12;2,-12;4,-11;5,-9;6,-7;6,-5;5,-3;4,-2;0,0/0,5;-1,6;0,7;1,6;0,5
@|-15,15|5,-4;4,-6;2,-8;0,-9;-2,-9;-4,-8;-6,-6;-7,-3;-7,-1;-6,2;-4,4;-2,5;0,5;2,4;4,2;5,-1/5,-4;5,2;6,4;8,5;10,5;12,4;13,2;14,-1;14,-3;13,-6;11,-9;9,-11;6,-13;3,-14;0,-14;-3,-13;-6,-11;-8,-9;-10,-6;-11,-3;-11,0;-10,3;-8,6;-6,8;-3,10;0,11;3,11;6,10;8,9
[|-7,7|-3,-16;-3,16/-3,-16;5,-16/-3,16;5,16
]|-7,7|-5,-16;3,-16;3,16/-5,16;3,16
^|-8,8|-8,2;0,-8;8,2
_|-9,9|-9,16;9,16
`|-5,5|1,-11;-1,-9;0,-8;1,-9
{|-8,8|2,-16;0,-14;-1,-12;-1,12;0,14;2,16/-1,-2;-3,0;-1,2/-6,0;-4,-1;-3,-2;-2,-4;-2,-6;-3,-8;-4,-9;-6,-10
}|-8,8|-2,-16;0,-14;1,-12;1,12;0,14;-2,16/1,-2;3,0;1,2/6,0;4,-1;3,-2;2,-4;2,-6;3,-8;4,-9;6,-10
~|-13,13|-9,3;-9,1;-8,-1;-7,-2;-5,-2;-3,-1;-1,1;1,3;3,4;5,4;7,3;8,2;9,0;9,-2
·|-3,3|0,0;1,0
—|-12,12|-10,0;10,0
"""


def load_font():
    table = {}
    for row in FONT_RAW.strip().split('\n'):
        fields = row.split('|')
        symbol = fields[0]
        left, right = (int(v) for v in fields[1].split(','))
        paths = []
        for part in fields[2].split('/'):
            points = []
            for token in part.split(';'):
                a, b = token.split(',')
                points.append((int(a), int(b)))
            paths.append(tuple(points))
        table[symbol] = (left, right, tuple(paths))
    return table


SANS = load_font()
SERIF = dict(SANS)
# Terminals turn the capitals of the display face into a serif cut.
TERMINALS = {
    'A': ((-8, 9), (8, 9), (0, -12)), 'B': ((-7, -12), (-7, 9), (-7, 2)),
    'D': ((-7, -12), (-7, 9), (-7, 2)), 'E': ((-6, -12), (-6, 9), (-6, 2)),
    'F': ((-6, -12), (-6, 9), (-6, 2)), 'H': ((-7, -12), (7, -12), (-7, 9), (7, 9)),
    'K': ((-7, -12), (7, -12), (-7, 9), (7, -12)),
    'M': ((-8, -12), (8, -12), (-8, 9), (8, 9)),
    'N': ((-7, -12), (7, -12), (-7, 9), (7, 9)),
    'R': ((-7, -12), (-7, 9), (7, 9)), 'T': ((0, 9), (-7, 9), (7, 9)),
    'U': ((-7, -12), (7, -12)), 'V': ((-8, -12), (8, -12)),
    'W': ((-10, -12), (10, -12), (-10, 9), (10, 9)),
    'X': ((-7, -12), (7, -12), (-7, 9), (7, 9)),
    'Y': ((-8, -12), (8, -12), (0, 9)),
    'Z': ((-7, -12), (7, -12), (-7, 9), (7, 9)),
    '1': ((1, 9), (-3, 9)), '2': ((-6, 9), (6, 9)), '4': ((3, 9),),
    '5': ((-5, 9), (5, 9)), '6': ((-5, 9), (6, 9)), '7': ((6, 9),),
}
for symbol, terminals in TERMINALS.items():
    left, right, paths = SERIF[symbol]
    caps = tuple(((x - 3, y), (x + 3, y)) for x, y in terminals)
    SERIF[symbol] = (min(left, min(x - 3 for x, _ in terminals)),
                     max(right, max(x + 3 for x, _ in terminals)), paths + caps)


def glyph_of(font, symbol):
    return font.get(symbol, font.get('·', (0, 8, ())))


def text_width(text, size, font=SANS, tracking=0.0, squeeze=1.0):
    if not text:
        return 0.0
    scale = size / 21.0
    total = sum((g[1] - g[0]) * scale * squeeze
                for g in (glyph_of(font, ch) for ch in text))
    return total + tracking * (len(text) - 1)


def put_text(sheet, x, y, text, size, col=INK, font=SANS, weight=1,
             tracking=0.0, squeeze=1.0, slant=0.0):
    scale = size / 21.0
    thick = max(1, int(round(weight * SS)))
    pen = x
    for ch in text:
        left, right, paths = glyph_of(font, ch)
        for path in paths:
            pts = []
            for gx, gy in path:
                px = pen + (gx - left) * scale * squeeze + slant * (9 - gy) * scale
                py = y + (gy + 12) * scale
                pts.append((px * SS, py * SS))
            if len(pts) > 1:
                sheet.outline(pts, col, thick)
        pen += (right - left) * scale * squeeze + tracking
    return pen - x


def put_centered(sheet, center, y, text, size, col=INK, font=SANS,
                 weight=1, tracking=0.0, squeeze=1.0, slant=0.0):
    width = text_width(text, size, font, tracking, squeeze)
    put_text(sheet, center - width / 2, y, text, size, col, font,
             weight, tracking, squeeze, slant)
    return width


def wrap(text, size, max_width, font=SANS, tracking=0.0, squeeze=1.0):
    lines = []
    current = ''
    for word in text.split():
        candidate = (current + ' ' + word).strip()
        if current and text_width(candidate, size, font, tracking, squeeze) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def put_wrapped(sheet, x, y, text, size, max_width, col=INK, font=SANS,
                weight=1, tracking=0.0, squeeze=1.0, leading=None):
    if leading is None:
        leading = size * 1.23
    lines = wrap(text, size, max_width, font, tracking, squeeze)
    for row, line in enumerate(lines):
        put_text(sheet, x, y + row * leading, line, size, col, font,
                 weight, tracking, squeeze)
    return len(lines), (len(lines) - 1) * leading + size


def fit_size(text, max_width, first, floor=7.0, font=SANS,
             tracking=0.0, squeeze=1.0):
    size = first
    while size > floor and text_width(text, size, font, tracking, squeeze) > max_width:
        size -= 0.5
    return size


def h_rule(sheet, x, y, width, col=INK, thick=1):
    sheet.rect(x * SS, y * SS, width * SS, max(1, int(thick * SS)), col)


def v_rule(sheet, x, y, height, col=INK, thick=1):
    sheet.rect(x * SS, y * SS, max(1, int(thick * SS)), height * SS, col)


def frame(sheet, x, y, width, height, fill=PAPER, edge=None, edge_weight=1):
    sheet.rect(x * SS, y * SS, width * SS, height * SS, fill)
    if edge is not None:
        t = max(1, int(edge_weight * SS))
        sheet.rect(x * SS, y * SS, width * SS, t, edge)
        sheet.rect(x * SS, (y + height) * SS - t, width * SS, t, edge)
        sheet.rect(x * SS, y * SS, t, height * SS, edge)
        sheet.rect((x + width) * SS - t, y * SS, t, height * SS, edge)


def caps(sheet, x, y, text, size, col=INK, font=SANS, weight=1,
         tracking=1.0, squeeze=1.0):
    return put_text(sheet, x, y, text.upper(), size, col, font,
                    weight, tracking, squeeze)


DATE_TEXT = 'SATURDAY 21 NOVEMBER 2026'
DATE_LINE = 'Saturday 21 November 2026'

REGION_NAMES = [
    ('RU', 'RUSSIA & UKRAINE', RED),
    ('EU', 'EUROPE', BLUE),
    ('ME', 'MIDDLE EAST', AMBER),
    ('AF', 'AFRICA', (120, 88, 52)),
    ('AS', 'ASIA', (52, 120, 96)),
    ('AM', 'AMERICAS', (140, 60, 90)),
    ('TB', 'TECH & BUSINESS', (70, 80, 110)),
]
CODE_NAME = {code: name for code, name, _ in REGION_NAMES}
REGION_TINT = {code: tint for code, _, tint in REGION_NAMES}
SHORT_REGION = {
    'RUSSIA & UKRAINE': 'RUSSIA-UKRAINE',
    'TECH & BUSINESS': 'TECH/BUSINESS',
}

STATS = [
    ('58,818', 'BITCOIN CLOSE / USD, NOV 21'),
    ('3,522', 'GOLD PER OUNCE / NOV 21'),
    ('92.57', 'BRENT CRUDE / USD A BARREL'),
    ('56,437', 'NIKKEI 225 / FRIDAY CLOSE'),
    ('74,736', 'GAZA DEATH TOLL / HEALTH AUTH.'),
    ('148', 'DRONES FIRED / AT UKRAINE'),
    ('4.0%', 'EURO INFLATION / OCTOBER'),
]

STORY_FIELDS = ('code', 'city', 'lon', 'lat', 'short', 'detail',
                'source', 'icon', 'impact')

STORY_TABLE = {
    1: ('RU', 'KRYVYI RIH', 33.4, 47.9,
        "Ballistic strike hits Zelenskyy's hometown",
        'Two killed and about 60 wounded in the central city.',
        'AP/REUTERS', 'missile', ''),
    2: ('RU', 'KYIV', 30.5, 50.5, '148 drones fired at Ukraine overnight',
        'The air force said 117 of the drones were shot down.',
        'RBC-UKRAINE', 'radar', '148'),
    3: ('RU', 'KYIV', 30.5, 50.5, 'Ukraine and UK sign deep-strike drone deal',
        'Kyiv and London agreed drone cooperation on Saturday.',
        'RBC-UKRAINE', 'radar', ''),
    4: ('RU', 'POLAND', 21.0, 52.0, '2,800 coalition troops train near border',
        'Ten countries drilled at Nowa Deba as missile strikes hit nearby.',
        'AFP', 'badge', '2,800'),
    5: ('RU', 'MOSCOW', 37.6, 55.8, 'Russia embraces US security talks offer',
        'Moscow used the opening to revive demands on NATO.',
        'AP', 'capitol', ''),
    6: ('RU', 'GULF OF FINLAND', 27.0, 60.0, 'Cargo ship damaged by drone strike',
        'Helsinki and Moscow both reported the hit on a sanctioned ship.',
        'POLITICO', 'radar', ''),
    7: ('EU', 'HELSINKI', 24.9, 60.2, 'Finland suspects Russian helicopter',
        'The ministry linked the incursion to a cargo-ship drone strike.',
        'NYT', 'radar', ''),
    8: ('EU', 'PARIS', 2.35, 48.9, 'Gen Z strike sweeps 25 countries',
        'Students marched on living costs, education and conscription.',
        'AFP/REUTERS', 'crowd', '25'),
    9: ('EU', 'PARIS', 2.35, 48.9, 'French protests enter sixth weekend',
        'The September movement marched again against prices and services.',
        'LE MONDE', 'crowd', ''),
    10: ('EU', 'GENEVA', 6.1, 46.2, 'UN killer-robot treaty talks collapse',
         'A consensus mandate was blocked and delegates adopted a weak pledge.',
         'REUTERS/GUARDIAN', 'robot', ''),
    11: ('EU', 'ANTALYA', 30.5, 36.9, 'COP31 climate talks end in deadlock',
         'Nearly 200 states stalled on fossil fuels at the resort.',
         'BBC/REUTERS', 'flame', '200'),
    12: ('EU', 'COPENHAGEN', 12.6, 55.7, 'Denmark accuses Russia of murder plot',
         'Officials alleged a plot against a US-Ukrainian rapper.',
         'BBC', 'badge', ''),
    13: ('EU', 'BRUSSELS', 4.35, 50.8, 'EU and UK move closer after reset',
         'Lengthy negotiations produced a closer post-Brexit arrangement.',
         'REUTERS', 'capitol', ''),
    14: ('EU', 'BRUSSELS', 4.35, 50.8, 'Chair proposes 44bn euro budget cut',
         'The EU leader suggested trimming the 2028-2034 budget.',
         'REUTERS', 'chart', '44BN'),
    15: ('EU', 'MADRID', -3.7, 40.4, 'Banking levy extended to fund housing',
         'Spain kept the levy in place through 2027 for housing policy.',
         'REUTERS', 'capitol', ''),
    16: ('EU', 'STOCKHOLM', 18.1, 59.3, 'Russian-linked firm collected data on Swedes',
         'A probe found secret collection of data on millions of people.',
         'GUARDIAN', 'chip', ''),
    17: ('EU', 'LONDON', -0.1, 51.5, 'UK patches fridge hack vulnerability',
         'Officials fixed a flaw after a wave of European hacks.',
         'BBC', 'chip', ''),
    18: ('EU', 'FRANKFURT', 8.7, 50.1, 'Euro inflation climbs to 4.0 percent',
         'Price growth in the euro area accelerated in October.',
         'EURONEWS', 'chart', '4.0%'),
    19: ('ME', 'HORMUZ', 56.5, 26.6, 'Iran strikes three tankers near Hormuz',
         'Tehran also unveiled a new underground missile launcher.',
         'AP/AL JAZEERA', 'tanker', '3'),
    20: ('ME', 'TEHRAN', 51.4, 35.7, 'Iran claims it hit a US F-16',
         'The claim said the jet was forced to land over the Gulf.',
         'AL JAZEERA', 'missile', ''),
    21: ('ME', 'GAZA', 34.5, 31.5, 'Gaza food truck strike kills three',
         'Health authorities reported the strike on an aid vehicle.',
         'AP', 'aid', '3'),
    22: ('ME', 'GAZA', 34.5, 31.5, 'Gaza death toll reaches 74,736',
         'The health authority tally was published on Saturday.',
         'AP', 'aid', '74,736'),
    23: ('ME', 'HODEIDAH', 42.9, 14.8, 'Coalition strikes Hodeidah; Houthis fire',
         'Riyadh came under fire as the coalition hit the port city.',
         'REUTERS', 'missile', ''),
    24: ('ME', 'TAIZ', 44.0, 13.6, 'Senior Houthi commander killed',
         'Government forces announced the killing in Taiz.',
         'AL JAZEERA', 'badge', ''),
    25: ('ME', 'TEHRAN', 51.4, 35.7, 'Iran keeps door open to diplomacy',
         'The foreign minister signalled willingness to end the war.',
         'REUTERS', 'capitol', ''),
    26: ('ME', 'BASRA', 47.8, 30.5, 'Power station fire kills at least four',
         'The blaze hit a power station in southern Iraq.',
         'REUTERS', 'flame', '4'),
    27: ('AF', 'BADME', 39.5, 13.2, 'Ethiopia, Eritrea trade fire near Badme',
         'The Horn of Africa frontier flared amid fears of a wider war.',
         'RIO TIMES', 'border', ''),
    28: ('AF', 'KHARTOUM', 32.5, 15.5, 'UN says 2,230 Sudan civilians killed',
         'The UN report attributed most of the deaths to drones.',
         'UN', 'crowd', '2,230'),
    29: ('AF', 'GOMA', 29.2, -1.7, '38 killed in eastern Congo church attack',
         'An ISIS-linked attack struck a church in the east of the country.',
         'DAILY NEWS EGYPT', 'aid', '38'),
    30: ('AF', 'BAYELSA', 6.3, 4.8, 'Funeral barge capsizes; rescue search',
         'Rescuers searched the waterway after the barge went down.',
         'DAILY POST', 'aid', ''),
    31: ('AF', 'PRETORIA', 28.2, -25.7, 'South Africa summons Nigerian envoy',
         'A broadcast dispute prompted the diplomatic summons.',
         'REUTERS', 'capitol', ''),
    32: ('AF', 'KAMPALA', 32.6, 0.3, 'Besigye faces November 25 hearing',
         'The opposition figure remained on bail conditions.',
         'RIO TIMES', 'capitol', ''),
    33: ('AF', 'CONAKRY', -13.7, 9.5, 'Guinea jails 202 miners',
         'A court jailed the miners and banned a broadcaster.',
         'REUTERS', 'badge', '202'),
    34: ('AF', 'COTONOU', 2.4, 9.5, 'Benin asks Paris for 35 artifacts',
         'The government requested the return of looted objects.',
         'AFRICANEWS', 'capitol', '35'),
    35: ('AS', 'TOKYO', 139.7, 35.7, 'Asian markets crash on AI sell-off',
         'Nikkei, Kospi and Taiex fell sharply in the Friday session.',
         'AKTZIEN/AP', 'chart', '-5%'),
    36: ('AS', 'TOKYO', 139.7, 35.7, 'Japan wary of regular trilateral',
         'Officials were cautious about a regular US-China-Russia format.',
         'JIJI PRESS', 'capitol', ''),
    37: ('AS', 'SEOUL', 127.0, 37.6, 'Ruling party moves to impeach justice',
         'The chief justice faced an impeachment push in Seoul.',
         'RIO TIMES', 'capitol', ''),
    38: ('AS', 'TOKYO', 139.7, 35.7, 'Japan weighs education minister exit',
         'The ruling party considered replacing him over a funds scandal.',
         'JIJI PRESS', 'capitol', ''),
    39: ('AS', 'KUALA LUMPUR', 101.7, 3.1, 'MSF warns on refugee registrations',
         'Suspension of UNHCR registration was said to endanger refugees.',
         'REUTERS', 'aid', ''),
    40: ('AS', 'SANTA CLARA', -121.9, 37.3, 'Trump urges Nvidia to take Huang back',
         'The president commented on the chipmaker leadership.',
         'REUTERS', 'chip', ''),
    41: ('AS', 'ISLAMABAD', 73.1, 33.7, 'UN spotlight on dissent in PoK',
         'A report highlighted repression of dissent in the region.',
         'REUTERS', 'crowd', ''),
    42: ('AM', 'MEXICO CITY', -99.1, 19.4, 'Mexico captures FBI most-wanted boss',
         'Eleven died in Sinaloa violence around the arrest.',
         'AP', 'badge', '11'),
    43: ('AM', 'TAPACHULA', -92.3, 14.9, 'Migrant caravan crosses into Mexico',
         'About 250 people entered the country at Tapachula.',
         'AP', 'crowd', '250'),
    44: ('AM', 'WASHINGTON', -77.0, 38.9, 'Pentagon restricts Canada defence ties',
         'A classified memo set new limits on cooperation.',
         'NYT', 'capitol', ''),
    45: ('AM', 'SAO PAULO', -46.6, -23.5, 'Bolsonaro in intensive care',
         'The former president was hospitalised with an obstruction.',
         'REUTERS', 'aid', ''),
    46: ('AM', 'WASHINGTON', -77.0, 38.9, 'Vance declines to back Iran nuclear claim',
         'The VP stopped short of endorsing the war rationale.',
         'NYT', 'capitol', ''),
    47: ('AM', 'WASHINGTON', -77.0, 38.9, 'Trump orders contractor inquiry clearance',
         'Federal contractors must clear inquiries with the White House.',
         'NYT', 'capitol', ''),
    48: ('TB', 'WALL STREET', -74.0, 40.7, 'S&P 500 and Dow enter correction',
         'The tech rout dragged the benchmarks into correction territory.',
         'BBC', 'chart', '-4%'),
    49: ('TB', 'WALL STREET', -74.0, 40.7, 'Bitcoin slides to one-year low',
         'ETF outflows continued as the coin broke below $59,000.',
         'COINGECKO', 'coin', '$58K'),
    50: ('TB', 'NEW YORK', -74.0, 40.7, 'Gold hovers near 14-month low',
         'Bullion stayed weak as hike fears persisted.',
         'REUTERS', 'coin', '$3,522'),
    51: ('TB', 'NEW YORK', -74.0, 40.7, 'CoreWeave symbol of AI buildout risk',
         'The debt-laden firm drew scrutiny as AI shares slid.',
         'NPR', 'chip', ''),
    52: ('TB', 'WASHINGTON', -77.0, 38.9, 'FBI probes crime database breach',
         'Agents investigated a hack of the national crime database.',
         'AP', 'chip', ''),
    53: ('TB', 'WASHINGTON', -77.0, 38.9, 'Judge approves Bayer Roundup settlement',
         'A court cleared the $7.25 billion settlement.',
         'REUTERS', 'capitol', '$7.25B'),
    54: ('TB', 'WASHINGTON', -77.0, 38.9, 'Trump seeks 10% credit card rate cap',
         'The proposal drew support from some Democrats.',
         'REUTERS', 'capitol', '10%'),
    55: ('TB', 'SAN FRANCISCO', -122.4, 37.8, 'Claude helped solve a math problem',
         'An Anthropic mathematician claimed a Holy Grail result.',
         'NPR', 'chip', ''),
    56: ('TB', 'MACAU', 113.5, 22.2, 'Hickman breaks 16-year lap record',
         'He won the Macau motorcycle Grand Prix on Saturday.',
         'BBC SPORT', 'badge', '16Y'),
}
STORIES = {ident: dict(zip(STORY_FIELDS, row))
           for ident, row in STORY_TABLE.items()}

HERO_IDS = (1, 10, 19)
CARD_IDS = (2, 7, 8, 11, 21, 22, 27, 29, 35, 42, 48, 49, 55, 56)
ALSO_IDS = (3, 4, 5, 6, 9, 12, 13, 14, 15, 16, 18, 20, 23, 24,
            25, 26, 28, 30, 31, 32, 34, 36, 37, 38, 39, 41, 44, 46, 50, 54)
LEFT_OUT_IDS = (33, 43, 45)
MAP_PIN_IDS = (2, 4, 6, 7, 9, 11, 12, 23, 26, 28, 30, 32, 34, 36, 42, 48)
HERO_TAGS = {1: 'KRYVYI RIH: MISSILE STRIKE',
             10: 'GENEVA: KILLER ROBOTS',
             19: 'HORMUZ: TANKERS HIT'}


def stamped(ident, number=None):
    record = dict(STORIES[ident])
    record['id'] = ident
    record['num'] = number
    record['pin'] = '%02d' % number if number is not None else ''
    return record


HEROES = [stamped(ident) for ident in HERO_IDS]
CARDS = [stamped(ident, number) for number, ident in enumerate(CARD_IDS, 1)]
ALSO = [stamped(ident, number)
        for number, ident in enumerate(ALSO_IDS, len(CARD_IDS) + 1)]
MAP_PINS = [item for item in CARDS + ALSO if item['id'] in MAP_PIN_IDS]
TOP3 = [record['short'] for record in HEROES]
LEFT_OUT = [
    'the %s jailed miners in Guinea' % STORIES[33]['impact'],
    "Bolsonaro's intensive-care stay",
    'the %s-person migrant caravan at Tapachula' % STORIES[43]['impact'],
]

PRESENTED = HEROES + CARDS + ALSO
STORY_COUNT = len(PRESENTED)
TOTAL_STORIES = len(STORIES)
PIN_COUNT = len(MAP_PINS)
REGION_COUNTS = {code: sum(1 for item in PRESENTED if item['code'] == code)
                 for code, _, _ in REGION_NAMES}
REGIONS = [(CODE_NAME[code], REGION_COUNTS[code], REGION_TINT[code])
           for code, _, _ in REGION_NAMES]
PICKED_IDS = HERO_IDS + CARD_IDS + ALSO_IDS + LEFT_OUT_IDS
assert len(set(PICKED_IDS)) == len(PICKED_IDS)


def draw_header(sheet):
    kicker = 'THE WORLD IN ONE DAY'
    kw = text_width(kicker, 9.5, SANS, 1.4, 0.9)
    caps(sheet, 996 - kw, 10, kicker, 9.5, RED, weight=2,
         tracking=1.4, squeeze=0.9)
    caps(sheet, 28, 11, DATE_TEXT, 8.5, GREY, weight=1,
         tracking=0.8, squeeze=0.88)

    put_centered(sheet, 512, 26, DATE_LINE, 52, INK, SERIF, weight=4,
                 tracking=0.4, squeeze=0.92)
    meta = ('%d STORIES - %d REGIONS - EVERY ONE DATED %s'
            % (STORY_COUNT, len(REGIONS), DATE_TEXT))
    meta_size = fit_size(meta, 940, 9.5, 7.0, SANS, 0.6, 0.86)
    caps(sheet, 28, 94, meta, meta_size, RED, weight=2,
         tracking=0.6, squeeze=0.86)

    lead = '  ·  '.join(TOP3)
    lead_size = fit_size(lead, 920, 13.8, 9.5, SERIF, 0.2, 0.95)
    put_centered(sheet, 512, 108, lead, lead_size, GREY, SERIF,
                 weight=1, tracking=0.2, squeeze=0.95, slant=0.13)
    h_rule(sheet, 28, 128, 968, INK, 2)
    h_rule(sheet, 28, 132, 968, RULE, 0.7)


def draw_stats(sheet):
    top, height, gap = 137, 45, 7
    cell = (968 - gap * (len(STATS) - 1)) / len(STATS)
    for index, (figure, caption) in enumerate(STATS):
        x = 28 + index * (cell + gap)
        v_rule(sheet, x, top + 2, height - 4, RED, 2)
        size = fit_size(figure, cell - 12, 19.0, 12.0, SANS, 0.2, 0.9)
        put_text(sheet, x + 7, top + 2, figure, size, INK, SANS,
                 weight=3, tracking=0.2, squeeze=0.9)
        pieces = [part.strip() for part in caption.split('/')]
        for row, part in enumerate(pieces[:2]):
            piece_size = fit_size(part, cell - 12, 8.4, 6.4,
                                  SANS, 0.3, 0.84)
            caps(sheet, x + 7, top + 27 + row * 9, part, piece_size,
                 GREY, weight=1, tracking=0.3, squeeze=0.84)
    h_rule(sheet, 28, 186, 968, RULE, 0.7)


def draw_regions(sheet):
    top, height = 190, 21
    total = sum(count for _, count, _ in REGIONS)
    cursor = 28.0
    for name, count, tint in REGIONS:
        width = 968.0 * count / total
        sheet.rect(cursor * SS, top * SS, width * SS, height * SS, tint)
        code = next(code for code, full, _ in REGION_NAMES if full == name)
        label = '%s %d' % (code, count)
        size = fit_size(label, width - 8, 8.6, 6.6, SANS, 0.2, 0.8)
        put_centered(sheet, cursor + width / 2, top + 5, label, size,
                     WHITE, SANS, weight=2, tracking=0.2, squeeze=0.8)
        sheet.rect(int((cursor + width - 1) * SS), top * SS, SS, height * SS, PAPER)
        cursor += width
    h_rule(sheet, 28, top, 968, RULE, 0.7)
    h_rule(sheet, 28, top + height, 968, RULE, 0.7)


def art_missile(sheet, x, y, w, h):
    h_rule(sheet, x, y + h - 9, w, (72, 82, 94), 1)
    for bx, bh in ((0.06, 0.22), (0.13, 0.36), (0.21, 0.17),
                   (0.76, 0.25), (0.84, 0.39), (0.92, 0.19)):
        sheet.rect((x + w * bx) * SS, (y + h - 9 - bh * h) * SS,
                   w * 0.05 * SS, bh * h * SS, (48, 56, 67))
    for mx, my, angle in ((0.20, 0.16, 0.92), (0.34, 0.06, 0.78), (0.50, 0.14, 1.02)):
        bx, by = x + w * mx, y + h * my
        ex = bx + math.cos(angle) * w * 0.18
        ey = by + math.sin(angle) * h * 0.34
        sheet.seg(bx * SS, by * SS, ex * SS, ey * SS, (226, 226, 216), 2 * SS)
        sheet.seg((bx - math.cos(angle) * 6) * SS, (by - math.sin(angle) * 6) * SS,
                  bx * SS, by * SS, AMBER, 3 * SS)
        sheet.disc(ex * SS, ey * SS, 4 * SS, RED)
    for radius, tint in ((16, RED), (10, AMBER), (5, (255, 232, 190))):
        sheet.disc((x + w * 0.72) * SS, (y + h * 0.40) * SS, radius * SS, tint)


def art_robot(sheet, x, y, w, h):
    cx, cy = x + w * 0.40, y + h * 0.44
    hw, hh = w * 0.30, h * 0.52
    sheet.rect((cx - hw / 2) * SS, (cy - hh / 2) * SS, hw * SS, hh * SS, (66, 76, 90))
    sheet.rect((cx - hw / 2 + 3) * SS, (cy - hh / 2 + 3) * SS,
               (hw - 6) * SS, (hh - 6) * SS, (46, 54, 66))
    sheet.disc((cx - hw * 0.22) * SS, (cy - hh * 0.08) * SS, 5 * SS, RED)
    sheet.disc((cx + hw * 0.22) * SS, (cy - hh * 0.08) * SS, 5 * SS, RED)
    for row in range(4):
        sheet.rect((cx - hw * 0.25) * SS, (cy + hh * 0.12 + row * 5) * SS,
                   hw * 0.5 * SS, 2 * SS, (104, 114, 128))
    sheet.seg(cx * SS, (cy - hh / 2) * SS, cx * SS, (cy - hh / 2 - 12) * SS,
              (150, 160, 175), 2 * SS)
    sheet.disc(cx * SS, (cy - hh / 2 - 14) * SS, 3 * SS, AMBER)
    bx, by, radius = x + w * 0.80, y + h * 0.40, 17
    sheet.disc(bx * SS, by * SS, radius * SS, RED, ring=True, weight=3 * SS)
    cross = radius * 0.65
    sheet.seg((bx - cross) * SS, (by - cross) * SS,
              (bx + cross) * SS, (by + cross) * SS, RED, 3 * SS)
    sheet.seg((bx - cross) * SS, (by + cross) * SS,
              (bx + cross) * SS, (by - cross) * SS, RED, 3 * SS)


def art_tanker(sheet, x, y, w, h):
    sea = y + h * 0.56
    sheet.rect(x * SS, sea * SS, w * SS, (y + h - sea) * SS, (36, 54, 72))
    for row in range(4):
        sheet.seg((x + 8) * SS, (sea + 7 + row * 9) * SS,
                  (x + w - 8) * SS, (sea + 7 + row * 9) * SS,
                  (58, 78, 98), SS)
    sx, sw, sy, sh = x + w * 0.16, w * 0.44, sea - 8, 18
    hull = [(sx, sy), (sx + sw, sy), (sx + sw * 0.90, sy + sh),
            (sx + sw * 0.08, sy + sh)]
    sheet.area([(px * SS, py * SS) for px, py in hull], (106, 112, 122))
    sheet.rect((sx + sw * 0.62) * SS, (sy - 16) * SS,
               sw * 0.18 * SS, 16 * SS, (132, 138, 144))
    sheet.disc((sx + sw * 0.35) * SS, (sy - 8) * SS, 10 * SS, AMBER)
    sheet.disc((sx + sw * 0.35) * SS, (sy - 13) * SS, 6 * SS, RED)
    bx, by = x + w * 0.80, y + h * 0.26
    sheet.disc(bx * SS, by * SS, 15 * SS, RED, ring=True, weight=3 * SS)
    sheet.seg((bx - 10) * SS, by * SS, (bx + 10) * SS, by * SS, RED, 3 * SS)
    sheet.seg(bx * SS, (by - 10) * SS, bx * SS, (by + 10) * SS, RED, 3 * SS)


HERO_ART = {'missile': art_missile, 'robot': art_robot, 'tanker': art_tanker}


def draw_heroes(sheet):
    top, height, gap = 223, 166, 12
    width = (968 - gap * 2) / 3
    for index, item in enumerate(HEROES):
        x = 28 + index * (width + gap)
        tag = HERO_TAGS[item['id']]
        fact = item['short'] + '. ' + item['detail']
        frame(sheet, x, top, width, height, DARK)
        h_rule(sheet, x, top, width, OXBLOOD, 3)
        tag_size = fit_size(tag, width - 24, 9.5, 7.5, SANS, 0.5, 0.84)
        tag_width = text_width(tag, tag_size, SANS, 0.5, 0.84) + 14
        sheet.rect((x + 9) * SS, (top + 9) * SS, tag_width * SS, 18 * SS, OXBLOOD)
        caps(sheet, x + 16, top + 13, tag, tag_size, WHITE,
             weight=2, tracking=0.5, squeeze=0.84)
        fact_size = 11.0
        _, used = put_wrapped(sheet, x + 10, top + 34, fact, fact_size,
                              width - 20, WHITE, SANS, weight=2,
                              tracking=0.1, squeeze=0.94, leading=13)
        art_y = top + 34 + used + 5
        art_h = top + height - 24 - art_y
        if art_h > 24:
            HERO_ART[item['icon']](sheet, x + 10, art_y, width - 20, art_h)
        caps(sheet, x + 10, top + height - 15, item['source'], 8, MUTED,
             weight=1, tracking=0.4, squeeze=0.86)


def clipped(text, size, max_width, count, font=SANS, tracking=0.0, squeeze=1.0):
    lines = wrap(text, size, max_width, font, tracking, squeeze)
    if len(lines) > count:
        lines = lines[:count]
        tail = lines[-1]
        while tail and text_width(tail + '..', size, font, tracking, squeeze) > max_width:
            tail = tail[:-1]
        lines[-1] = tail + '..'
    return lines


def card_icon(sheet, x, y, kind, tint):
    span = 15
    sheet.rect(x * SS, y * SS, span * SS, span * SS, tint)
    cx, cy = x + span / 2, y + span / 2
    if kind == 'flame':
        sheet.area([(cx * SS, (y + 2) * SS), ((cx + 4) * SS, (y + 9) * SS),
                    (cx * SS, (y + 13) * SS), ((cx - 4) * SS, (y + 9) * SS)], WHITE)
    elif kind == 'radar':
        sheet.disc(cx * SS, cy * SS, 5 * SS, WHITE, ring=True, weight=SS)
        sheet.seg(cx * SS, cy * SS, (cx + 4) * SS, (cy - 3) * SS, WHITE, SS)
    elif kind == 'crowd':
        for dx, dy in ((-4, 4), (0, 1), (4, 4)):
            sheet.disc((cx + dx) * SS, (cy + dy) * SS, 2 * SS, WHITE)
    elif kind == 'aid':
        sheet.rect((cx - 1) * SS, (y + 2) * SS, 2 * SS, 11 * SS, WHITE)
        sheet.rect((x + 2) * SS, (cy - 1) * SS, 11 * SS, 2 * SS, WHITE)
    elif kind == 'border':
        sheet.seg((x + 2) * SS, (cy + 4) * SS, (x + 13) * SS, (cy - 4) * SS, WHITE, 2 * SS)
        sheet.seg((x + 2) * SS, (cy - 4) * SS, (x + 13) * SS, (cy + 4) * SS, WHITE, 2 * SS)
    elif kind == 'chart':
        sheet.outline([((x + 2) * SS, (y + 3) * SS), ((x + 6) * SS, (y + 7) * SS),
                       ((x + 9) * SS, (y + 5) * SS), ((x + 13) * SS, (y + 12) * SS)],
                      WHITE, 2 * SS)
    elif kind == 'badge':
        sheet.disc(cx * SS, cy * SS, 5 * SS, WHITE)
        sheet.disc(cx * SS, cy * SS, 2 * SS, tint)
    elif kind == 'coin':
        sheet.disc(cx * SS, cy * SS, 5 * SS, WHITE, ring=True, weight=2 * SS)
        sheet.seg((cx - 2) * SS, cy * SS, (cx + 2) * SS, cy * SS, WHITE, SS)
    elif kind == 'chip':
        sheet.rect((cx - 4) * SS, (cy - 4) * SS, 8 * SS, 8 * SS, WHITE)
        for off in (-4, 0, 4):
            sheet.seg((cx + off) * SS, (cy - 6) * SS, (cx + off) * SS, (cy - 4) * SS, WHITE, SS)
            sheet.seg((cx + off) * SS, (cy + 4) * SS, (cx + off) * SS, (cy + 6) * SS, WHITE, SS)
    else:
        sheet.area([((cx - 5) * SS, (cy - 1) * SS), (cx * SS, (cy - 6) * SS),
                    ((cx + 5) * SS, (cy - 1) * SS)], WHITE)
        for off in (-4, 0, 4):
            sheet.rect((cx + off - 1) * SS, cy * SS, 2 * SS, 6 * SS, WHITE)


def draw_cards(sheet):
    top, height, gap_x, gap_y = 397, 98, 10, 10
    columns = 7
    width = (968 - gap_x * (columns - 1)) / columns
    for index, item in enumerate(CARDS):
        column, row = divmod(index, columns)
        x = 28 + column * (width + gap_x)
        y = top + row * (height + gap_y)
        frame(sheet, x, y, width, height, PALE, RULE, 0.7)
        sheet.rect(x * SS, y * SS, width * SS, 19 * SS, OXBLOOD)
        tint = REGION_TINT[item['code']]
        put_text(sheet, x + 6, y + 4, item['pin'], 9.5, WHITE, SANS, weight=3)
        city = item['city']
        city_size = fit_size(city, width - 55, 7.6, 6.2, SANS, 0.15, 0.8)
        city_w = text_width(city, city_size, SANS, 0.15, 0.8) + 8
        sheet.rect((x + 24) * SS, (y + 3) * SS, city_w * SS, 13 * SS,
                   (234, 223, 214))
        caps(sheet, x + 28, y + 5, city, city_size, OXBLOOD,
             weight=2, tracking=0.15, squeeze=0.8)
        card_icon(sheet, x + width - 18, y + 3, item['icon'], tint)
        head_lines = clipped(item['short'], 8.8, width - 12, 3,
                             SANS, 0.05, 0.93)
        for line_no, line in enumerate(head_lines):
            put_text(sheet, x + 6, y + 24 + line_no * 10.5, line, 8.8,
                     INK, SANS, weight=2, tracking=0.05, squeeze=0.93)
        body_lines = clipped(item['detail'], 7.4, width - 12, 2,
                             SANS, 0, 0.95)
        for line_no, line in enumerate(body_lines):
            put_text(sheet, x + 6, y + 60 + line_no * 8.5, line, 7.4,
                     (74, 68, 60), SANS, weight=1, squeeze=0.95)
        caps(sheet, x + 6, y + height - 11, item['source'], 6.8,
             (116, 110, 100), weight=1, tracking=0.25, squeeze=0.86)
        if item['impact']:
            width_impact = text_width(item['impact'], 7, SANS, 0, 0.84)
            caps(sheet, x + width - 6 - width_impact, y + height - 11,
                 item['impact'], 7, OXBLOOD, weight=2, squeeze=0.84)


LAND_SHAPES = [
    [(-168, 65), (-140, 70), (-125, 60), (-100, 55), (-80, 50), (-60, 47),
     (-55, 25), (-80, 8), (-100, 15), (-120, 30), (-130, 50), (-160, 55)],
    [(-80, 10), (-60, 5), (-35, -5), (-20, -15), (-35, -35), (-50, -55),
     (-70, -50), (-75, -20)],
    [(-10, 36), (0, 44), (30, 45), (45, 40), (60, 30), (90, 25), (110, 20),
     (120, 35), (140, 45), (160, 60), (130, 70), (80, 72), (40, 70),
     (10, 60), (-5, 50)],
    [(-15, 35), (10, 35), (30, 30), (45, 12), (40, -15), (25, -35),
     (10, -35), (-5, -20), (-15, 5)],
    [(110, -10), (140, -12), (155, -28), (150, -40), (130, -38), (115, -25)],
    [(-50, 60), (-30, 70), (-20, 80), (-45, 83), (-60, 75)],
]


def draw_map(sheet, x, y, width, height):
    frame(sheet, x, y, width, height, PAPER, RULE, 0.7)
    heading = 'WHERE THE DAY HAPPENED  -  %d PINS' % PIN_COUNT
    caps(sheet, x + 8, y + 6, heading, 9, BLUE,
         weight=2, tracking=0.5, squeeze=0.86)
    mx, my = x + 10, y + 24
    mw, mh = width - 20, height - 34

    def project(lon, lat):
        return (mx + (lon + 180.0) / 360.0 * mw,
                my + (90.0 - lat) / 180.0 * mh)

    for gy in range(0, int(mh), 15):
        for gx in range(0, int(mw), 15):
            sheet.rect((mx + gx) * SS, (my + gy) * SS, SS, SS, RULE)
    for shape in LAND_SHAPES:
        pts = [project(lon, lat) for lon, lat in shape]
        scaled = [(px * SS, py * SS) for px, py in pts]
        sheet.area(scaled, (166, 181, 201))
        sheet.outline(scaled + [scaled[0]], BLUE, SS, closed=False)
    placed = []
    for item in MAP_PINS:
        px, py = project(item['lon'], item['lat'])
        for attempt in range(32):
            offset = 0 if attempt == 0 else 5 + 3 * (attempt - 1)
            angle = attempt * 2.399963
            cx = max(mx + 11, min(mx + mw - 11, px + math.cos(angle) * offset))
            cy = max(my + 11, min(my + mh - 11, py + math.sin(angle) * offset))
            if all((cx - ox) ** 2 + (cy - oy) ** 2 >= 19 ** 2
                   for ox, oy in placed):
                break
        placed.append((cx, cy))
        sheet.disc(cx * SS, cy * SS, 10 * SS, RED)
        sheet.disc(cx * SS, cy * SS, 10 * SS, WHITE, ring=True, weight=2 * SS)
        put_centered(sheet, cx, cy - 4, item['pin'], 7.5, WHITE, SANS, weight=2)


def draw_also(sheet, x, y, width, height):
    put_text(sheet, x, y, 'ALSO ON ' + DATE_TEXT, 11, RED, SANS,
             weight=3, tracking=0.4, squeeze=0.9)
    h_rule(sheet, x, y + 17, width, INK, 1)
    column_width = (width - 12) / 2
    half = (len(ALSO) + 1) // 2
    for index, item in enumerate(ALSO):
        column, row = divmod(index, half)
        cx = x + column * (column_width + 12)
        ry = y + 24 + row * 15.0
        put_text(sheet, cx, ry, item['pin'], 8, OXBLOOD, SANS, weight=2)
        city_size = fit_size(item['city'], 66, 7.4, 6.2, SANS, 0.1, 0.8)
        caps(sheet, cx + 16, ry, item['city'], city_size, INK,
             weight=2, tracking=0.1, squeeze=0.8)
        source = item['source']
        source_w = text_width(source, 6.5, SANS, 0, 0.84)
        show_source = source_w < 58
        room = column_width - 92 - (source_w + 4 if show_source else 0)
        line = clipped(item['short'], 7.2, room, 1, SANS, 0, 0.94)[0]
        put_text(sheet, cx + 88, ry, line, 7.2, (64, 60, 54),
                 SANS, weight=1, squeeze=0.94)
        if show_source:
            caps(sheet, cx + column_width - source_w, ry, source, 6.5,
                 MUTED, weight=1, squeeze=0.84)


def draw_bottom(sheet):
    draw_also(sheet, 28, 603, 540, 258)
    draw_map(sheet, 580, 603, 416, 258)


def draw_datecheck(sheet):
    frame(sheet, 28, 869, 968, 74, PAPER, RED, 1.5)
    sheet.rect(38 * SS, 879 * SS, 92 * SS, 18 * SS, RED)
    caps(sheet, 44, 882, 'DATE CHECK', 9, WHITE, weight=2,
         tracking=0.5, squeeze=0.86)
    omitted = ("Left out as Friday 20 November's news: " + '; '.join(LEFT_OUT) + '.')
    lines = clipped(omitted, 10, 840, 2, SANS, 0.1, 0.95)
    for row, line in enumerate(lines):
        put_text(sheet, 142, 879 + row * 13, line, 10, INK, SANS,
                 weight=1, tracking=0.1, squeeze=0.95)
    closing = ('Every story here happened, or was first reported, '
               'on %s.' % DATE_TEXT)
    put_text(sheet, 38, 910, closing, 10.5, RED, SANS,
             weight=2, tracking=0.15, squeeze=0.95)


def draw_footer(sheet):
    h_rule(sheet, 28, 952, 968, INK, 1)
    note = ('SOURCES: AP, AFP, Reuters, BBC, Al Jazeera, Jiji Press, RBC-Ukraine, '
            'POLITICO, Rio Times and the agencies credited on every story.')
    put_centered(sheet, 512, 960, note, 8.5, GREY, SANS, weight=1,
                 tracking=0.25, squeeze=0.9)
    note2 = ('%d STORIES REVIEWED - %d PRESENTED - ALL DATED %s'
             % (TOTAL_STORIES, STORY_COUNT, DATE_TEXT))
    put_centered(sheet, 512, 977, note2, 8, MUTED, SANS, weight=1,
                 tracking=0.5, squeeze=0.9)


def draw_test_f(sheet):
    size = 600.0
    scale = size / 21.0
    y = SIDE / 2.0 - 13.0 * scale
    put_centered(sheet, SIDE / 2.0, y, 'F', size, INK, SANS, weight=6)


def main():
    folder = os.path.dirname(OUT)
    if folder:
        os.makedirs(folder, exist_ok=True)
    sheet = Sheet()
    if os.environ.get('MAKEFUN_TEST_F') == '1':
        draw_test_f(sheet)
        blob = write_png('/tmp/ftest.png', SIDE, SIDE, sheet.reduce())
        print('TEST-F sha256=%s bytes=%d'
              % (hashlib.sha256(blob).hexdigest(), len(blob)))
        return
    draw_header(sheet)
    draw_stats(sheet)
    draw_regions(sheet)
    draw_heroes(sheet)
    draw_cards(sheet)
    draw_bottom(sheet)
    draw_datecheck(sheet)
    draw_footer(sheet)
    rgb = sheet.reduce()
    blob = write_png(OUT, SIDE, SIDE, rgb)
    digest = hashlib.sha256(blob).hexdigest()
    print('BUILD-DONE sha256=%s bytes=%d stories=%d' %
          (digest, len(blob), STORY_COUNT))


if __name__ == '__main__':
    main()
