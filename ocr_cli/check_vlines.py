# -*- coding: utf-8 -*-
import sys, os, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import analysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pdf = os.path.join(ROOT, '1150729.pdf')
pages = st.render_pages(pdf, 200)

for i, img in enumerate(pages):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hl, vl, rs = analysis.find_lines_robust(gray, return_rowsums=True)
    strengths = [float(max(rs[max(0, y - 3):y + 4])) for y in hl]
    ftype, rows = analysis.row_bands(hl, strengths)
    print(f'p{i+1}: {ftype} rows={len(rows)}')
    print(f'  hl={hl}')
    print(f'  vl={vl}')
    if ftype == '中型':
        for j, (y0, y1) in enumerate(rows):
            band_h = y1 - y0
            print(f'  band{j+1}: y={y0}-{y1} h={band_h}')
        print(f'  arrange grid: {analysis.detect_arrange_grid(gray, rows)}')
    print()
