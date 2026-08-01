# -*- coding: utf-8 -*-
"""列填寫偵測 v2:背景正規化墨量,並 OCR 空列確認"""
import os, sys, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect_lib as dl
import structure as st
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG = os.path.join(ROOT, 'debug')


def norm_ink(gray, y0, y1, x0, x1, vlines, bgk=51, thr=40):
    """背景正規化後的暗像素量(排除格線)"""
    bg = cv2.medianBlur(gray, bgk)
    norm = cv2.subtract(bg, gray)
    _, bw = cv2.threshold(norm, thr, 255, cv2.THRESH_BINARY)
    band = bw[y0 + 4:y1 - 4, x0:x1]
    for vx in vlines:
        if x0 - 2 <= vx <= x1 + 2:
            band[:, max(0, vx - 2 - x0):min(band.shape[1], vx + 3 - x0)] = 0
    return int((band > 0).sum())


if __name__ == '__main__':
    out = []
    for pdf in ['1150729.pdf']:
        pages = st.render_pages(pdf, 200)
        for i, img in enumerate(pages):
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hl, vl = dl.find_lines_robust(g)
            ftype, rows = dl.row_bands(hl)
            out.append('== %s p%d %s rows=%d' % (pdf, i + 1, ftype, len(rows)))
            for j, (a, b) in enumerate(rows):
                ink = norm_ink(g, a, b, vl[0], vl[-1], vl)
                out.append('   r%02d ink=%d %s' % (j + 1, ink, 'FILLED' if ink > 500 else 'empty'))
    with open(os.path.join(DEBUG, 'diag_rowink2.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('done')
