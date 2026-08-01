# -*- coding: utf-8 -*-
import csv, glob, os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np

out = []
with open(os.path.join('csv', '115.07.29.csv'), encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    out.append('HEADER: ' + json.dumps(r.fieldnames, ensure_ascii=False))
    out.append('ROWS: ' + json.dumps([(x['類型'], x['時段'], x['番數']) for x in r], ensure_ascii=False))

with open(os.path.join('csv', '115.07.24.csv'), encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    out.append('0724 ROWS: ' + json.dumps([(x['類型'], x['時段'], x['番數']) for x in r], ensure_ascii=False))

img = st.render_pages('1150729.pdf', 200)[0]
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
hl, vl, *_ = st.find_lines(g)
out.append('0729 p1: h_lines=%d v_lines=%d' % (len(hl), len(vl)))
out.append('  hl[:6]=%s' % hl[:6])
out.append('  hl[-4:]=%s' % hl[-4:])
out.append('  vl[:8]=%s' % vl[:8])
out.append('  vl[-6:]=%s' % vl[-6:])

with open(os.path.join('debug', 'gt_detail.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')
