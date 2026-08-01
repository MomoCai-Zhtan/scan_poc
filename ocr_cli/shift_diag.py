# -*- coding: utf-8 -*-
"""診斷小頁時段框:對全部小頁比較多種墨跡指標 vs GT"""
import csv, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import check_v4 as c4
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def gt_first_shift(day):
    csvs = glob.glob(os.path.join(ROOT, 'csv', day + '*.csv'))
    if not csvs:
        return None
    with open(csvs[0], encoding='utf-8-sig') as f:
        r = list(csv.DictReader(f))
    return r[0]['時段'] if r else None

def alt_metrics(gray, box):
    x0, y0, x1, y1, _ = box
    inner = gray[y0 + 2:y1 - 2, x0 + 2:x1 - 2]
    if inner.size == 0:
        return 0, 0
    return float(inner.mean()), float((inner < 128).sum()) / inner.size

out = []
for pdf in sorted(glob.glob(os.path.join(ROOT, '*.pdf'))):
    name = os.path.basename(pdf)
    try:
        pages = st.render_pages(pdf, 200)
    except Exception as e:
        out.append('%s ERR %s' % (name, e))
        continue
    for i, img in enumerate(pages):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        boxes = c4.find_check_boxes(gray)
        res = c4.decide_shift(boxes, gray)
        if not res:
            out.append('%s p%d boxes=0' % (name, i + 1))
            continue
        am, pm, da, dp = res
        ama, amr = alt_metrics(gray, am)
        pma, pmr = alt_metrics(gray, pm)
        out.append('%s p%d | da=%d dp=%d d-diff=%d | mean %.1f/%.1f ratio %.2f/%.2f' %
                   (name, i + 1, da, dp, da - dp, ama, pma, amr, pmr))
with open(os.path.join(ROOT, 'debug', 'shift_diag.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')
