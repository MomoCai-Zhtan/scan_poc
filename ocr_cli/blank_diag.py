# -*- coding: utf-8 -*-
"""空白表單樣本診斷:印刷樣版的列結構"""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
import numpy as np
import structure as st
import analysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in sorted(glob.glob(os.path.join(ROOT, '*.pdf'))):
    name = os.path.basename(path)
    if name[0].isdigit():
        continue
    pages = st.render_pages(path, 200)
    for i, img in enumerate(pages):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hl, vl = analysis.find_lines_robust(gray)
        ftype, rows = analysis.row_bands(hl)
        gaps = [(b - a) for a, b in zip(hl[:-1], hl[1:])]
        from collections import Counter
        c = Counter(g // 10 * 10 for g in gaps)
        print('%s p%d size=%s hl=%d gaps=%s type=%s rows=%d' %
              (repr(name), i + 1, img.shape[:2][::-1], len(hl),
               dict(sorted(c.items())), ftype, len(rows)))
