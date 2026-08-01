# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np

out = []
for pdf in ['1150729.pdf', '1150724.pdf', '1150702.pdf']:
    pages = st.render_pages(pdf, 200)
    for i, img in enumerate(pages):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        binv = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15)
        kh = max(3, w // 15); kline_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kh, 1))
        kv = max(3, h // 15); kline_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv))
        horiz = cv2.morphologyEx(binv, cv2.MORPH_OPEN, kline_h)
        vert = cv2.morphologyEx(binv, cv2.MORPH_OPEN, kline_v)
        colsums = vert.sum(axis=0) / 255
        rowsums = horiz.sum(axis=1) / 255
        thr_h = w * 0.25
        thr_v = h * 0.25
        hl = st.cluster(np.where(rowsums > thr_h)[0], 8)
        vl = st.cluster(np.where(colsums > thr_v)[0], 8)
        out.append('== %s p%d size=%dx%d' % (pdf, i + 1, w, h))
        out.append('  hl=%d vl=%d (thr_h=%.0f thr_v=%.0f)' % (len(hl), len(vl), thr_h, thr_v))
        out.append('  rowsum>0.25h count: %d; max colsum=%.0f (need >%.0f)' %
                   ((rowsums > thr_h).sum(), colsums.max(), thr_v))
        out.append('  #cols above 0.5h: %d; above 0.3h: %d' %
                   ((colsums > h * 0.5).sum(), (colsums > h * 0.3).sum()))
        # skew angle via minAreaRect of the binarized table region (middle band)
        band = binv[h // 4: 3 * h // 4, w // 8: 7 * w // 8]
        pts = cv2.findNonZero(band)
        if pts is not None and len(pts) > 1000:
            (cx, cy), (bw_, bh_), ang = cv2.minAreaRect(pts)
            out.append('  minAreaRect angle=%.3f size=%.0fx%.0f' % (ang, bw_, bh_))
with open(os.path.join('debug', 'diag_0729.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')
