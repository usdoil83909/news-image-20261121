#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, '/root/makefun/news21-entry')
import main

def probe_string(text, font, font_name, size=60):
    sheet = main.Sheet()
    # Draw at x=100, y=100
    main.put_text(sheet, 100, 100, text, size, main.INK, font)
    # Get pixel data directly from super-sampled sheet (sheet.px, size PIX x PIX where PIX = 1024*3 = 3072)
    # Or from sheet.reduce() (SIDE x SIDE = 1024 x 1024)
    # Let's use reduced pixels: 1024x1024 RGB
    rgb = sheet.reduce()
    
    # Bounding box of ink around x=100..500, y=100..400 (scaled by 1)
    # pen=100, y=100, size=60 -> text height ~ size, scale = 60/21 = 2.85. y goes from y to y + ~35
    # Let's scan y from 80 to 200, x from 80 to 500
    cols = [0] * 1024
    grid = []
    min_x, max_x = 1024, 0
    min_y, max_y = 1024, 0
    for y in range(80, 220):
        row_str = ""
        for x in range(80, 500):
            off = (y * 1024 + x) * 3
            r, g, b = rgb[off], rgb[off+1], rgb[off+2]
            is_ink = (r, g, b) != main.PAPER
            if is_ink:
                cols[x] += 1
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                row_str += "#"
            else:
                row_str += "."
        grid.append(row_str)
    
    if min_x > max_x:
        print(f"Font: {font_name}, Text: '{text}' -> NO INK FOUND")
        return
        
    print(f"=== Font: {font_name}, Text: '{text}' ===")
    print(f"Bounding Box: x=[{min_x}..{max_x}], y=[{min_y}..{max_y}]")
    
    # Print column histogram of ink for the region [min_x..max_x]
    col_hist = [cols[x] for x in range(min_x, max_x + 1)]
    print("Column ink histogram:", col_hist)
    
    # Crop grid to ink bounding box
    crop_grid = []
    for y in range(min_y, max_y + 1):
        row = ""
        for x in range(min_x, max_x + 1):
            off = (y * 1024 + x) * 3
            is_ink = (rgb[off], rgb[off+1], rgb[off+2]) != main.PAPER
            row += "#" if is_ink else "."
        crop_grid.append(row)
    
    # Print compact ASCII grid (downsample horizontally/vertically if wide)
    print("ASCII Grid:")
    for row in crop_grid:
        print(row)

if __name__ == "__main__":
    for font_name, font in [('SANS', main.SANS), ('SERIF', main.SERIF)]:
        probe_string('L', font, font_name)
        probe_string('P', font, font_name)
        probe_string('5', font, font_name)
        probe_string('2', font, font_name)
