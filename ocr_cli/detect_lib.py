# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np


def find_lines_robust(gray, thr_frac=0.10, vfrac=0.10):
    bg = cv2.medianBlur(gray, 101)
    norm = cv2.subtract(bg, gray)
    _, bw = cv2.threshold(norm, 40, 255, cv2.THRESH_BINARY)
    h, w = gray.shape
    kh = max(3, w // 15); kline_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kh, 1))
    kv = max(3, h // 15); kline_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kline_h)
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kline_v)
    rowsums = horiz.sum(axis=1) / 255
    colsums = vert.sum(axis=0) / 255
    hl = st.cluster(np.where(rowsums > w * thr_frac)[0], 8)
    vl = st.cluster(np.where(colsums > h * vfrac)[0], 8)
    return hl, vl


def detect_table_cells(img_bgr, min_w=15, min_h=15, min_area=400):
    """偵測表格儲存格,支援合併儲存格(rowspan/colspan)與只涵蓋部分寬高的局部子分隔線
    (例如中型表單「管模/時間」子列只在窄欄內才有橫線,不會貫穿整頁寬度)。

    作法:把橫線遮罩與縱線遮罩疊成一張「格線圖」,用輪廓的巢狀關係(RETR_TREE)取
    沒有子輪廓的最內層輪廓——那正好對應實際被線框住的最小儲存格,不論該儲存格是
    否跨了好幾個子列/子欄。比起「整頁寬度覆蓋率門檻 + 逐列逐欄做笛卡兒積」的作法,
    這裡不需要假設整張表都是均勻網格。

    回傳 (cells, h_lines, v_lines):
      cells   依讀取順序(上到下、左到右)排序的 [{x,y,w,h}, ...]
      h_lines/v_lines 由各 cell 邊界聚類得出,僅供畫參考格線用。
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 11, 5)
    h, w = bw.shape

    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 30, 1))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horiz_kernel, iterations=1)
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 30))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vert_kernel, iterations=1)

    grid = cv2.bitwise_or(horiz, vert)
    grid = cv2.dilate(grid, np.ones((3, 3), np.uint8), iterations=1)

    contours, hierarchy = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return [], [], []
    hierarchy = hierarchy[0]

    cells = []
    for i, c in enumerate(contours):
        if hierarchy[i][2] != -1:  # 有子輪廓 -> 不是最內層儲存格
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        if cw < min_w or ch < min_h or cw * ch < min_area:
            continue
        if cw > w * 0.98 and ch > h * 0.98:  # 整頁外框保險
            continue
        cells.append({'x': int(x), 'y': int(y), 'w': int(cw), 'h': int(ch)})

    cells.sort(key=lambda c: (c['y'], c['x']))

    def cluster(vals, threshold=10):
        vals = sorted(vals)
        if not vals:
            return []
        clusters = [[vals[0]]]
        for v in vals[1:]:
            if v - clusters[-1][-1] <= threshold:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        return [int(np.mean(c)) for c in clusters]

    h_lines = cluster([c['y'] for c in cells] + [c['y'] + c['h'] for c in cells])
    v_lines = cluster([c['x'] for c in cells] + [c['x'] + c['w'] for c in cells])

    return cells, h_lines, v_lines


def row_bands(hl):
    """回傳 (型別, 番次列 [(y0,y1)...])。資料列區 = hline 之後間距進入穩定列高模式。"""
    gaps = [(a, b - a) for a, b in zip(hl[:-1], hl[1:])]
    # 主間距:統計 40~300 之間間距的眾數
    gs = np.array([g for _, g in gaps if 40 <= g <= 300])
    if len(gs) == 0:
        return '未知', []
    vals, counts = np.unique(np.clip(gs // 10 * 10, 40, 300), return_counts=True)
    mode = int(vals[np.argmax(counts)])
    if mode <= 70:
        ftype = '小型'
        target = 60
        lo, hi = 50, 70
        span = 1
    else:
        ftype = '中型'
        target = 88
        lo, hi = 70, 110
        span = 3
    # 從第一個進入模式(或後續)的間距起算
    start = None
    for i, (y, g) in enumerate(gaps):
        if lo <= g <= hi:
            start = i
            break
    if start is None:
        return ftype, []
    ys = hl[start:]
    rows = []
    if span == 1:
        for a, b in zip(ys[:-1], ys[1:]):
            rows.append((a, b))
    else:
        # 中型:合併到 ~264px(3×88) 一列
        acc = ys[0]
        idx = 1
        while idx < len(ys):
            g = ys[idx] - acc
            if g >= 240:  # 已達 264±24
                rows.append((acc, ys[idx]))
                acc = ys[idx]
            idx += 1
        if idx == len(ys) and rows and rows[-1][1] < ys[-1]:
            rows.append((acc, ys[-1]))
    return ftype, rows


_CHECK_TPL = None
_TPL_TYPE = None


def load_check_tpl(tpl_path, btype):
    global _CHECK_TPL, _TPL_TYPE
    img = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
    _CHECK_TPL = cv2.resize(img, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_AREA)
    _TPL_TYPE = btype


def detect_checkboxes(img):
    """以樣板比對定位上午/下午勾選框,回傳 (box_am, box_pm, checked_am_dark, checked_pm_dark)"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    tpl = _CHECK_TPL
    th, tw = tpl.shape
    band = g[170:270, 0:700]
    res = cv2.matchTemplate(band, tpl, cv2.TM_CCOEFF_NORMED)
    _, _, _, maxloc = cv2.minMaxLoc(res)
    # 找兩個 peak
    best = []
    while len(best) < 2:
        _, mx, _, mxloc = cv2.minMaxLoc(res)
        score = mx
        if score < 0.4:
            break
        best.append((mxloc[0], mxloc[1] + 170, score))
        # 遮掉這個 peak 附近
        x, y, _ = best[-1]
        res[max(0, y - 170 - th):min(band.shape[0], y - 170 + th), max(0, x - tw):min(band.shape[1], x + tw)] = -1
    best.sort()
    if len(best) == 0:
        return None, None, 0, 0
    bx = [b[0] for b in best]
    cy = int(np.mean([b[1] + th / 2 for b in best]))
    boxes = []
    for x, y, s in best:
        cx = x + tw // 2
        boxes.append((cx, cy))
    if len(boxes) == 2:
        am = min(boxes, key=lambda b: b[0])
        pm = max(boxes, key=lambda b: b[0])
    else:
        am = boxes[0]
        pm = None
    da = interior_ink(g, am) if am else 0
    dp = interior_ink(g, pm) if pm else 0
    return am, pm, da, dp


def interior_ink(g, center, size=34):
    cx, cy = center
    x0, y0 = cx - size // 2, cy - size // 2
    inner = g[y0 + 5 : y0 + size - 5, x0 + 5 : x0 + size - 5]
    if inner.size == 0:
        return 0
    return int((inner < 130).sum())


if __name__ == '__main__':
    out = []
    tpl = os.path.join('debug', 'check_tpl.png')
    # 用 07.02 p2 的 上午 空框做樣板(縮小取核心)
    img0 = st.render_pages('1150702.pdf', 200)[1]
    g0 = cv2.cvtColor(img0, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(tpl, g0[198:232, 95:130])
    load_check_tpl(tpl, '中型')
    for pdf in ['1150729.pdf', '1150724.pdf', '1150702.pdf', '1150721.pdf']:
        pages = st.render_pages(pdf, 200)
        for i, img in enumerate(pages):
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hl, vl = find_lines_robust(g)
            ftype, rows = row_bands(hl)
            am, pm, da, dp = detect_checkboxes(img)
            res = '上午' if da > dp else '下午'
            out.append('%s p%d hl=%d vl=%d %s rows=%d' % (pdf, i + 1, len(hl), len(vl), ftype, len(rows)))
            out.append('   check: am=%s pm=%s ink am=%d pm=%d -> %s' % (am, pm, da, dp, res))
            out.append('   rows: %s' % rows)
    with open(os.path.join('debug', 'diag_bands2.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('done')
