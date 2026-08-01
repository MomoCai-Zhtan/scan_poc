# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np


def find_lines_robust(gray, thr_frac=0.10, vfrac=0.10):
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
    hl = st.cluster(np.where(rowsums > w * thr_frac)[0], 8)
    vl = st.cluster(np.where(colsums > h * vfrac)[0], 8)
    return hl, vl


img = st.render_pages('1150729.pdf', 200)[0]
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
hl, vl = find_lines_robust(g)
annot = img.copy()
for y in hl:
    cv2.line(annot, (0, y), (annot.shape[1], y), (0, 0, 255), 2)
for x in vl:
    cv2.line(annot, (x, 0), (x, annot.shape[0]), (0, 255, 0), 2)
cv2.imwrite(os.path.join('debug', '0729_p1_robust_lines.png'), annot)
out = ['hl=%d vl=%s' % (len(hl), vl)]
bg = cv2.medianBlur(g, 101)
norm = cv2.subtract(bg, g)
_, bw = cv2.threshold(norm, 40, 255, cv2.THRESH_BINARY)
h, w = g.shape
kv = max(3, h // 15); kline_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv))
vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kline_v)
colsums = vert.sum(axis=0) / 255
# top 40 columns with their sums
idx = np.argsort(colsums)[::-1][:40]
out.append('top40 cols: ' + ', '.join('%d:%d' % (x, colsums[x]) for x in sorted(idx)))
with open(os.path.join('debug', 'diag_0729_vlines.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')
