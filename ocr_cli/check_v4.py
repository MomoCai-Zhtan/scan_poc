# -*- coding: utf-8 -*-
"""勾選框偵測 v4:精確 bbox,span 過濾文字,精確內芯比墨"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np


def find_check_boxes(gray, top=185, bottom=250, xmax=700, edge_h=14, pair_min=22, pair_max=45):
    bg = cv2.medianBlur(gray, 51)
    norm = cv2.subtract(bg, gray)
    _, bw = cv2.threshold(norm, 45, 255, cv2.THRESH_BINARY)
    band = bw[top:bottom, 0:xmax]
    h = band.shape[0]
    col = np.zeros(xmax, dtype=int)
    for x in range(xmax):
        run = mx = 0
        for y in range(h):
            if band[y, x] > 0:
                run += 1
                if run > mx:
                    mx = run
            else:
                run = 0
        col[x] = mx
    xs = np.where(col >= edge_h)[0]
    groups = []
    if len(xs):
        start = prev = xs[0]
        for v in xs[1:]:
            if v - prev > 6:
                groups.append((start + prev) // 2)
                start = v
            prev = v
        groups.append((start + prev) // 2)
    boxes = []
    used = set()
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            d = groups[j] - groups[i]
            if pair_min <= d <= pair_max and i not in used and j not in used:
                x0, x1 = groups[i], groups[j]
                block = band[:, x0 - 1:x1 + 2]
                rowsum = (block > 0).sum(axis=1)
                ys = np.where(rowsum >= (x1 - x0) * 0.5)[0]
                if len(ys) < 2:
                    continue
                y0, y1y = ys[0], ys[-1]
                span = y1y - y0
                boxes.append((x0, y0 + top, x1, y1y + top, span))
                used.add(i)
                used.add(j)
                break
    boxes.sort()
    return boxes


def box_ink(gray, x0, y0, x1, y1, inset=4, thresh=150):
    inner = gray[y0 + inset:y1 - inset, x0 + inset:x1 - inset]
    if inner.size == 0:
        return 0
    return int((inner < thresh).sum())


def decide_shift(boxes, gray):
    """回傳 (上午box, 下午box) 或 None"""
    real = [b for b in boxes if b[4] >= 22]
    if len(real) >= 2:
        # 取最左與最右
        am = real[0]
        pm = real[-1]
    elif len(real) == 1:
        # 只剩一個:以 x 位置猜(小於140=上午,否則下午),配對另一側再偵測
        return None
    else:
        return None
    da = box_ink(gray, *am[:4])
    dp = box_ink(gray, *pm[:4])
    return am, pm, da, dp


if __name__ == '__main__':
    out = []
    for pdf in ['1150729.pdf', '1150724.pdf', '1150702.pdf', '1150721.pdf']:
        pages = st.render_pages(pdf, 200)
        for i, img in enumerate(pages):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            boxes = find_check_boxes(gray)
            s = ['(%d,%d)w%d h%d' % (b[0], b[1], b[2] - b[0], b[4]) for b in boxes]
            res = decide_shift(boxes, gray)
            if res:
                am, pm, da, dp = res
                r = '上午' if da > dp else '下午'
            else:
                am = pm = None
                da = dp = 0
                r = '?'
            out.append('%s p%d boxes=%s | am=%s ink=%d pm=%s ink=%d -> %s' %
                       (pdf, i + 1, '; '.join(s), am, da, pm, dp, r))
    with open(os.path.join('debug', 'diag_check_v4.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('done')
