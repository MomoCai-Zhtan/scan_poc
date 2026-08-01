# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np

BOXES = {
    '中型': {'am': (95,196,130,232), 'pm': (229,196,264,232)},
    '小型': {'am': (53,189,85,222),  'pm': (178,189,210,222)},
}

def interior(g, b):
    x0, y0, x1, y1 = b
    inner = g[y0+4:y1-4, x0+4:x1-4]
    return int((inner < 130).sum()), inner.size

if __name__ == '__main__':
    out = []
    for pdf in ['1150721.pdf', '1150702.pdf', '1150724.pdf', '1150729.pdf']:
        pages = st.render_pages(pdf, 200)
        out.append('== %s' % pdf)
        for i, img in enumerate(pages):
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hl, vl, *_ = st.find_lines(g)
            gaps = [b - a for a, b in zip(hl[:-1], hl[1:])]
            med = int(np.median(gaps)) if gaps else 0
            ftype = '中型' if len(vl) >= 14 and med > 100 else ('小型' if len(vl) >= 18 else '?')
            if ftype not in BOXES:
                out.append('  p%d type=%s skip' % (i + 1, ftype))
                continue
            b = BOXES[ftype]
            da, _ = interior(g, b['am'])
            dp, _ = interior(g, b['pm'])
            res = '上午' if da > dp else '下午'
            out.append('  p%d type=%s am_dark=%d pm_dark=%d -> %s' % (i + 1, ftype, da, dp, res))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'debug', 'check_test.txt'),
              'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('done')
