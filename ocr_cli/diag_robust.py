# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np


def find_lines_robust(gray):
    bg = cv2.medianBlur(gray, 101)
    norm = cv2.subtract(bg, gray)
    _, bw = cv2.threshold(norm, 40, 255, cv2.THRESH_BINARY)
    h, w = gray.shape
    kh = max(3, w // 15); kline_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kh, 1))
    kv = max(3, h // 15); kline_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kline_h)
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kline_v)
    rowsums = horiz.sum(axis=1) / 255
    colsums = vert.sum(axis=0) / 255
    thr_h = w * 0.15
    thr_v = h * 0.15
    hl = st.cluster(np.where(rowsums > thr_h)[0], 8)
    vl = st.cluster(np.where(colsums > thr_v)[0], 8)
    return hl, vl


out = []
for pdf in ['1150729.pdf', '1150724.pdf', '1150702.pdf', '1150721.pdf']:
    pages = st.render_pages(pdf, 200)
    for i, img in enumerate(pages):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hl, vl = find_lines_robust(g)
        gaps = [b - a for a, b in zip(hl[:-1], hl[1:])]
        med = int(np.median(gaps)) if gaps else 0
        ftype = '中型' if len(vl) >= 14 and med > 100 else ('小型' if len(vl) >= 18 else '?')
        out.append('%s p%d hl=%d vl=%d medgap=%d -> %s' % (pdf, i + 1, len(hl), len(vl), med, ftype))
with open(os.path.join('debug', 'diag_robust.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')
