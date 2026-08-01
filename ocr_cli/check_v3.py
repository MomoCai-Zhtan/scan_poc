# -*- coding: utf-8 -*-
"""勾選框偵測 v3:表頭帶找垂直線段 → 配對成方框 → 內部墨跡比對"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np


def find_check_boxes(gray, top=185, bottom=245, xmax=700, edge_h=16, pair_min=24, pair_max=40):
    """回傳 [(cx, cy, inner_ink, ring_ink)] 由左而右。無 → []"""
    bg = cv2.medianBlur(gray, 51)
    norm = cv2.subtract(bg, gray)
    _, bw = cv2.threshold(norm, 45, 255, cv2.THRESH_BINARY)
    band = bw[top:bottom, 0:xmax]
    grayband = gray[top:bottom, 0:xmax]
    h = band.shape[0]
    # 每個欄位的連續暗色段長
    edge_cols = []
    col = np.zeros(xmax, dtype=int)
    for x in range(xmax):
        run = 0
        mx = 0
        for y in range(h):
            if band[y, x] > 0:
                run += 1
                if run > mx:
                    mx = run
            else:
                run = 0
        col[x] = mx
    xs = np.where(col >= edge_h)[0]
    # 叢集相鄰欄(容差 6) → 邊線群
    groups = []
    if len(xs):
        start = prev = xs[0]
        for v in xs[1:]:
            if v - prev > 6:
                groups.append((start + prev) // 2)
                start = v
            prev = v
        groups.append((start + prev) // 2)
    # 配對:兩群距離在範圍內
    boxes = []
    used = set()
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            d = groups[j] - groups[i]
            if pair_min <= d <= pair_max and i not in used and j not in used:
                x0, x1 = groups[i], groups[j]
                cx = (x0 + x1) // 2
                # 找方框的上下緣:在此 x 範圍內,行總和的尖峰
                block = band[:, x0 - 1:x1 + 2]
                rowsum = (block > 0).sum(axis=1)
                ys = np.where(rowsum >= (x1 - x0) * 0.5)[0]
                if len(ys) < 2 or ys[-1] - ys[0] < 14:
                    continue
                y0, y1 = ys[0], ys[-1]
                cy = (y0 + y1) // 2 + top
                inner = grayband[y0 + 5:y1 - 4, x0 + 5:x1 - 4]
                ring_all = grayband[y0 - 2:y1 + 3, x0 - 2:x1 + 3]
                ink_in = (inner < 130).sum() / max(1, inner.size)
                ink_ring = (ring_all < 130).sum() / max(1, ring_all.size)
                boxes.append((cx, cy, ink_in, ink_ring))
                used.add(i)
                used.add(j)
                break
    boxes.sort()
    return boxes


def interior_ink(gray, cx, cy, size=30):
    x0, y0 = cx - size // 2, cy - size // 2
    inner = gray[y0 + 5:y0 + size - 5, x0 + 5:x0 + size - 5]
    if inner.size == 0:
        return 0
    return int((inner < 130).sum())


if __name__ == '__main__':
    out = []
    for pdf in ['1150729.pdf', '1150724.pdf', '1150702.pdf', '1150721.pdf']:
        pages = st.render_pages(pdf, 200)
        for i, img in enumerate(pages):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            boxes = find_check_boxes(gray)
            s = []
            for b in boxes:
                s.append('box@%d,%d ink_in=%.2f ring=%.2f' % (b[0], b[1], b[2], b[3]))
            res = '?'
            if len(boxes) >= 2:
                da = interior_ink(gray, boxes[0][0], boxes[0][1])
                dp = interior_ink(gray, boxes[1][0], boxes[1][1])
                res = '上午' if da > dp else '下午'
            else:
                da = dp = 0
            out.append('%s p%d : %s | inka=%d inkp=%d -> %s' % (pdf, i + 1, '; '.join(s), da, dp, res))
    with open(os.path.join('debug', 'diag_check_v3.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('done')
