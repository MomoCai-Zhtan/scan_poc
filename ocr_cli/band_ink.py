# -*- coding: utf-8 -*-
"""逐列手寫墨跡測試:能否區分「有填寫」vs「空白」列"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
import numpy as np
import structure as st
import analysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def band_ink(gray, y0, y1, thresh=150):
    """列內墨跡比例。排除邊界線帶(每邊 6px)、排除最左 90px(番次欄)與最右 30px。"""
    m = 6
    strip = gray[y0 + m:y1 - m, 90:gray.shape[1] - 30]
    if strip.size == 0:
        return 0.0
    return float((strip < thresh).sum()) / strip.size

def band_ink2(gray, y0, y1):
    """超暗墨(手寫):mean<thresh 的比例 + <90 比例"""
    m = 6
    strip = gray[y0 + m:y1 - m, 90:gray.shape[1] - 30]
    if strip.size == 0:
        return 0.0, 0.0
    return (float((strip < 110).sum()) / strip.size,
            float((strip < 90).sum()) / strip.size)

for pdf in ['1150729.pdf', '1150702.pdf']:
    pages = st.render_pages(os.path.join(ROOT, pdf), 200)
    for i, img in enumerate(pages):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hl, vl = analysis.find_lines_robust(gray)
        ftype, rows = analysis.row_bands(hl)
        print('== %s p%d %s' % (pdf, i + 1, ftype))
        for k, (a, b) in enumerate(rows):
            ink = band_ink(gray, a, b)
            i110, i90 = band_ink2(gray, a, b)
            print('  %2d %4d-%4d ink=%.4f <110=%.4f <90=%.4f %s' %
                  (k + 1, a, b, ink, i110, i90,
                   '#' * int(i110 * 2000)))
