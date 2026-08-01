# -*- coding: utf-8 -*-
"""把中型頁的偵測列框疊在影像上存 PNG,供檢視對齊"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
import numpy as np
import structure as st
import analysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBG = os.path.join(ROOT, 'debug')

for pdf in ['1150729.pdf', '1150702.pdf']:
    path = os.path.join(ROOT, pdf)
    pages = st.render_pages(path, 200)
    for i, img in enumerate(pages):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hl, vl = analysis.find_lines_robust(gray)
        ftype, rows = analysis.row_bands(hl)
        if ftype != '中型':
            continue
        annot = img.copy()
        for a, b in rows:
            cv2.rectangle(annot, (0, a), (annot.shape[1] - 1, b), (0, 0, 255), 3)
            cv2.putText(annot, str(len([1 for x, y in rows if (x, y) == (a, b)])) if False else '',
                        (30, a + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        for k, (a, b) in enumerate(rows):
            cv2.putText(annot, '%d番' % (k + 1), (40, a + 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 255), 4)
        # 垂直線也畫上
        for x in vl:
            cv2.line(annot, (x, 0), (x, annot.shape[0]), (0, 200, 0), 1)
        out = os.path.join(DBG, 'mid_%s_p%d.png' % (pdf.replace('.pdf', ''), i + 1))
        ok, buf = cv2.imencode('.png', annot)
        with open(out, 'wb') as f:
            f.write(buf.tobytes())
        print(out)
