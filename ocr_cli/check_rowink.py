# -*- coding: utf-8 -*-
"""列填寫偵測:每列墨量(排除格線)判空/填"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect_lib as dl
import structure as st
import cv2
import numpy as np


def row_ink(gray, y0, y1, x0, x1, vlines):
    band = gray[y0 + 4:y1 - 4, x0:x1]
    mask = np.ones_like(band, dtype=bool)
    # 排除垂直格線
    for vx in vlines:
        if x0 - 2 <= vx <= x1 + 2:
            mask[:, max(0, vx - 2 - x0):min(band.shape[1], vx + 3 - x0)] = False
    dark = (band < 130) & mask
    return int(dark.sum())


if __name__ == '__main__':
    out = []
    for pdf in ['1150729.pdf', '1150721.pdf', '1150702.pdf']:
        pages = st.render_pages(pdf, 200)
        for i, img in enumerate(pages):
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hl, vl = dl.find_lines_robust(g)
            ftype, rows = dl.row_bands(hl)
            out.append('== %s p%d %s rows=%d' % (pdf, i + 1, ftype, len(rows)))
            for j, (a, b) in enumerate(rows):
                ink = row_ink(g, a, b, vl[0], vl[-1], vl)
                out.append('   r%02d y=%d-%d ink=%d %s' % (j + 1, a, b, ink, 'FILLED' if ink > 250 else 'empty'))
    with open(os.path.join('debug', 'diag_rowink.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('done')
