# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect_lib as dl
import structure as st
import cv2

out = []
for pdf in ['1150729.pdf', '1150702.pdf']:
    pages = st.render_pages(pdf, 200)
    for i, img in enumerate(pages):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hl, vl = dl.find_lines_robust(g)
        gaps = [b - a for a, b in zip(hl[:-1], hl[1:])]
        out.append('== %s p%d hl=%d' % (pdf, i + 1, len(hl)))
        for a, b in zip(hl, gaps if len(gaps) == len(hl) else gaps + [None]):
            pass
        # 顯示 hl 與 gap 對照
        for j in range(len(hl)):
            gap = gaps[j] if j < len(gaps) else None
            out.append('  hl[%d]=%d gap=%s' % (j, hl[j], gap))
with open(os.path.join('debug', 'diag_hgaps.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')
