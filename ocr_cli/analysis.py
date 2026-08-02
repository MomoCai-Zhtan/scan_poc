# -*- coding: utf-8 -*-
"""頁面分析:型別、番次列區、時段、日期 — 供 B 工具使用"""
import os
import re
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import check_v4
import ocrx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG = os.path.join(ROOT, 'debug')


def find_lines_robust(gray, thr_frac=0.10, vfrac=0.10, return_rowsums=False):
    bg = cv2.medianBlur(gray, 101)
    norm = cv2.subtract(bg, gray)
    _, bw = cv2.threshold(norm, 40, 255, cv2.THRESH_BINARY)
    h, w = gray.shape
    kh = max(3, w // 15)
    kline_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kh, 1))
    kv = max(3, h // 15)
    kline_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kline_h)
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kline_v)
    rowsums = horiz.sum(axis=1) / 255
    colsums = vert.sum(axis=0) / 255
    hl = st.cluster(np.where(rowsums > w * thr_frac)[0], 8)
    vl = st.cluster(np.where(colsums > h * vfrac)[0], 8)
    if return_rowsums:
        return hl, vl, rowsums
    return hl, vl


def row_bands(hl, strengths=None):
    """回傳 (型別, [(y0,y1)...] 番次列)。
    小型: 每番次 = 3 子列(以上下強線為邊界; 無 strengths 時退回位置法, 每 3 條線取第 3 條)。
    中型: 每番次 264px。"""
    gaps = [(a, b - a) for a, b in zip(hl[:-1], hl[1:])]
    gs = np.array([g for _, g in gaps if 40 <= g <= 300])
    if len(gs) == 0:
        return '未知', []
    vals, counts = np.unique(np.clip(gs // 10 * 10, 40, 300), return_counts=True)
    mode = int(vals[np.argmax(counts)])
    if mode <= 70:
        ftype = '小型'
    else:
        ftype = '中型'

    if ftype == '小型':
        bounds = None
        if strengths is not None and len(strengths) == len(hl):
            med = float(np.median(strengths))
            thr = 1.4 * med
            strong = [y for y, s in zip(hl, strengths) if s > thr]
            if len(strong) >= 2:
                bounds = strong
        if bounds is None:
            bounds = [hl[i] for i in range(2, len(hl), 3)]
        out = [bounds[0]]
        for b in bounds[1:]:
            gap = b - out[-1]
            if gap > 240:
                target = out[-1] + 180
                diffs = [abs(x - target) for x in hl]
                k = int(np.argmin(diffs))
                out.append(hl[k] if diffs[k] <= 25 else target)
            out.append(b)
        return ftype, [(a, b) for a, b in zip(out[:-1], out[1:])]
    else:
        start = None
        for i, (y, g) in enumerate(gaps):
            if g >= 150:
                start = i
                break
        if start is None:
            return ftype, []
        # 邊界線 = 每 264px 一條(比對偵測線, 容差 20px)
        pos = hl[start]
        bounds = [pos]
        last = hl[-1]
        while True:
            target = pos + 264
            if target > last + 20:
                break
            diffs = [abs(x - target) for x in hl]
            k = int(np.argmin(diffs))
            if diffs[k] <= 20:
                pos = hl[k]
            else:
                pos = target
            bounds.append(pos)
        rows = [(bounds[k], bounds[k + 1]) for k in range(len(bounds) - 1)]
        return ftype, rows


def detect_arrange_grid(gray, rows, x0=960, x1=1250):
    """中型 C12 模具排列順序:每番次切成 4 格(4 個模具欄位, 跨全番次高)。
    回傳 {band_index: [(x,y,w,h)... 4 方框(依 x 排序)]}。
    圓圈淡漏偵測時以等分欄補齊。"""
    if not rows:
        return {}
    band_h = max(b - a for a, b in rows)
    centers = []
    for y0, y1 in rows:
        reg = gray[y0:y1, x0:x1]
        _, bw = cv2.threshold(reg, 150, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if 25 <= w <= 100 and 40 <= h <= 130 and cv2.contourArea(c) > 800:
                centers.append(x + x0 + w // 2)
    cols = sorted(st.cluster(sorted(centers), 24)) if centers else []
    ideal = [x0 + (2 * k + 1) * (x1 - x0) // 8 for k in range(4)]
    if len(cols) < 4:
        cols = ideal
    elif len(cols) > 4:
        cols = sorted(min(cols, key=lambda c: abs(c - t)) for t in ideal)
    half = (x1 - x0) // 8
    grid = {}
    for bi, (y0, y1) in enumerate(rows):
        boxes = []
        for c in cols:
            xl = max(x0, c - half)
            xr = min(x1, c + half)
            boxes.append((xl, y0, xr - xl, band_h))
        grid[bi] = boxes
    return grid


def decide_shift_typeaware(ftype, res):
    """中型:單邊無墨,墨跡判別可靠。小型:兩框墨跡太接近,單邊無墨才信墨跡,否則用先驗(下午)。"""
    if not res:
        return None, 0
    am, pm, da, dp = res
    if ftype == '中型':
        return ('上午' if da > dp else '下午'), abs(da - dp)
    if da == 0 and dp > 0:
        return '下午', dp
    if dp == 0 and da > 0:
        return '上午', da
    return '下午', abs(da - dp)


def detect_mid_columns(vl):
    """Map vertical lines to medium-form column boundaries (C1~C16).
    Returns dict {'C1':(x0,x1), ...} or None if insufficient v_lines."""
    labels = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8',
              'C9', 'C10', 'C11', 'C12', 'C13', 'C14', 'C15', 'C16']
    if len(vl) < len(labels) + 1:
        return None
    cols = {}
    for i, label in enumerate(labels):
        cols[label] = (vl[i], vl[i + 1])
    return cols


def mid_band_layout(y0, y1, cols, r2_offset=176):
    """Compute crop coordinates for a medium-form band.

    Each band (264px) splits into R1 (176px, top) and R2 (88px, bottom).
    C14/C15 each have 3 sub-rows within R1; C3~C7 R2 holds centrifuge time.

    Returns dict with crop tuples (x, y, w, h) per field group.
    """
    r2_y = y0 + r2_offset
    r1_h = r2_y - y0
    r2_h = y1 - r2_y

    c14_x0, c14_x1 = cols['C14']
    c15_x0, c15_x1 = cols['C15']
    c3_x0 = cols['C3'][0]
    c7_x1 = cols['C7'][1]

    sub_h = r1_h // 3
    c14_cells = []
    c15_cells = []
    for k in range(3):
        ry0 = y0 + k * sub_h
        ry1 = y0 + (k + 1) * sub_h
        c14_cells.append((c14_x0, ry0, c14_x1 - c14_x0, ry1 - ry0))
        c15_cells.append((c15_x0, ry0, c15_x1 - c15_x0, ry1 - ry0))

    centrifuge = (c3_x0, r2_y, c7_x1 - c3_x0, r2_h)

    return {
        'r2_y': r2_y,
        'centrifuge': centrifuge,
        'c14_cells': c14_cells,
        'c15_cells': c15_cells,
    }


def _band_missing(b):
    """Return list of field names missing from a parsed band (needs OCR retry)."""
    m = []
    if not b.get('item'):
        m.append('item')
    if len(b.get('speeds', [])) < 4:
        m.append('speeds')
    if len(b.get('speed_times', [])) < 4:
        m.append('speed_times')
    if not b.get('centrifuge') or not b['centrifuge'][0]:
        m.append('centrifuge')
    if not b.get('steam_pool'):
        m.append('steam_pool')
    nonempty = sum(1 for x in (b.get('molds') or []) if x)
    if 0 < nonempty != 3:
        m.append('molds')
    if not b.get('c14'):
        m.append('c14')
    if not b.get('c15'):
        m.append('c15')
    return m


def _band_has_ink(b):
    return bool(b.get('item') or b.get('molds') or b.get('speeds')
                or b.get('centrifuge') or b.get('steam_pool'))


def _merge_band(t, s):
    """Fill missing slots of band dict t with values from s (retry result)."""
    for k in ('item', 'steam_pool'):
        if not t.get(k) and s.get(k):
            t[k] = s[k]
    for k in ('speeds', 'speed_times'):
        tv = t.get(k) or []
        sv = s.get(k) or []
        n = max(len(tv), len(sv))
        merged = []
        for i in range(n):
            a = tv[i] if i < len(tv) else ''
            b = sv[i] if i < len(sv) else ''
            merged.append(a or b)
        t[k] = merged
    # molds: 中型 canonically has 3 non-empty; replace when retry is more canonical
    tv = t.get('molds') or []
    sv = s.get('molds') or []
    tn = sum(1 for x in tv if x)
    sn = sum(1 for x in sv if x)
    if sn == 3 and tn != 3:
        t['molds'] = sv
    elif sn == 0:
        pass
    else:
        n = max(len(tv), len(sv))
        merged = []
        for i in range(n):
            a = tv[i] if i < len(tv) else ''
            b = sv[i] if i < len(sv) else ''
            merged.append(a or b)
        t['molds'] = merged
    if not t.get('centrifuge') or not t['centrifuge'][0]:
        s_c = s.get('centrifuge') or ('', '')
        if s_c[0]:
            t['centrifuge'] = [s_c[0], s_c[1]]
    for k in ('c14', 'c15'):
        tv = t.get(k) or []
        sv = s.get(k) or []
        if not tv and sv:
            t[k] = sv


def _retry_missing_bands(pdf_path, page_index, rows, bands, max_retry=4):
    """Per-band crop OCR (band + header context) for bands with missing fields."""
    retry_list = []
    for bi in range(len(rows)):
        b = bands.get(bi, {})
        if _band_missing(b) and _band_has_ink(b):
            retry_list.append(bi)
    retry_list = retry_list[:max_retry]
    for bi in retry_list:
        y0, y1 = rows[bi]
        try:
            md = ocrx.ocr_band_with_header(pdf_path, page_index, y0, y1)
            if not md:
                continue
            parsed = ocrx.parse_mid_table(md)
            if not parsed:
                continue
            _merge_band(bands.setdefault(bi, {}), parsed.get(0, {}))
        except Exception:
            continue
    return bands


def _retry_c14c15(pdf_path, page_index, rows, bands, mid_layout):
    """Per-cell crop OCR for C14/C15 sub-rows where full-page OCR returned empty.

    C14/C15 cells are narrow (72x58px) — full-page OCR often misses them on
    sparse-ink PDFs. This crops each column's 3 sub-cells as a single stacked
    image at 3x enlargement (2 API calls per band instead of 6).
    """
    if not mid_layout or not mid_layout.get('bands'):
        return bands
    cell_bands = mid_layout['bands']
    for bi in range(len(rows)):
        if bi >= len(cell_bands):
            continue
        b = bands.get(bi, {})
        c14 = b.get('c14', [])
        c15 = b.get('c15', [])
        if c14 and c15:
            continue
        layout = cell_bands[bi]

        if not c14:
            try:
                md = ocrx.ocr_c14c15_crop(pdf_path, page_index, layout['c14_cells'])
                if md:
                    b['c14'] = _extract_2digit(md)[:3]
            except Exception:
                pass
            if 'c14' not in b:
                b['c14'] = []

        if not c15:
            try:
                md = ocrx.ocr_c14c15_crop(pdf_path, page_index, layout['c15_cells'])
                if md:
                    b['c15'] = _extract_2digit(md)[:3]
            except Exception:
                pass
            if 'c15' not in b:
                b['c15'] = []
    return bands


def _extract_2digit(markdown):
    """Extract 2-digit number strings from OCR markdown (for C14/C15 temps/times)."""
    import re
    out = []
    for line in markdown.split('\n'):
        for n in re.findall(r'(\d{2})', line):
            out.append(n)
    return out[:3]


def _add_arrange_order(pdf_path, page_index, rows, bands, arrange_boxes):
    """C13 模具排列順序: per-band crop OCR the circled digits, cross-check vs 轉位.

    Only expose arrange when >=2 digits read (single-digit reads are unreliable);
    the frontend then falls back to auto-copy 排列←轉位.
    """
    for bi, boxes in arrange_boxes.items():
        if bi >= len(rows) or not boxes:
            continue
        b = bands.get(bi, {})
        if not (b.get('molds') and any(b['molds'])):
            continue
        x0 = max(0, boxes[0][0] - 1)
        y0 = rows[bi][0]
        x1 = min(boxes[-1][0] + boxes[-1][2] + 1, 1653)
        y1 = rows[bi][1]
        try:
            md = ocrx.ocr_crop(pdf_path, page_index, x0, y0, x1 - x0, y1 - y0, scale=3)
            arr = ocrx.parse_arrange_circles(md) if md else []
        except Exception:
            arr = []
        if len(arr) < 2:
            b['arrange'] = []
            continue
        molds = b.get('molds', [])
        nm = sum(1 for m in molds if m)
        arr = (list(arr) + [''] * 4)[:4]
        if nm == 3:
            # 3 個模具: 排列1,2,4 (排列3 留空) ← 模具 1,2,3
            arr = [arr[0], arr[1], '', arr[2]]
            pos_map = [0, 1, -1, 2]
        else:
            pos_map = [0, 1, 2, 3]
        conflict = False
        for i, a in enumerate(arr):
            mi = pos_map[i]
            if mi < 0 or mi >= nm or not a:
                continue
            if molds[mi] and a != molds[mi]:
                conflict = True
        b['arrange'] = arr
        b['arrange_conflict'] = conflict


def ocr_auto_fields(pdf_path, page_index, rows, arrange_boxes=None, mid_layout=None):
    """Hybrid OCR for auto-fillable fields.

    Strategy: full-page OCR first (1 API call), then per-band crop retry for
    bands with missing fields (sparse-ink columns), then C13 circled-digit OCR
    per band for the 模具排列順序 cross-check, then per-cell C14/C15 crop retry
    for narrow-column sparse ink.

    Returns dict {band_index: {field_name: value}} per band.
    """
    try:
        markdown = ocrx.ocr_page(pdf_path, page_index)
        if not markdown:
            bands = {}
        else:
            bands = ocrx.parse_mid_table(markdown)
        bands = _retry_missing_bands(pdf_path, page_index, rows, bands)
        if arrange_boxes:
            _add_arrange_order(pdf_path, page_index, rows, bands, arrange_boxes)
        bands = _retry_c14c15(pdf_path, page_index, rows, bands, mid_layout)
        return bands
    except Exception:
        return {}


def page_analysis(pdf_path, page_index, ocr_arrange=True, ocr=True):
    img = st.render_pages(pdf_path, 200)[page_index]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hl, vl, rowsums = find_lines_robust(gray, return_rowsums=True)
    strengths = [float(max(rowsums[max(0, y - 3):y + 4])) for y in hl]
    ftype, rows = row_bands(hl, strengths)
    boxes = check_v4.find_check_boxes(gray)
    res = check_v4.decide_shift(boxes, gray)
    shift, conf = decide_shift_typeaware(ftype, res)
    result = {
        'page': page_index + 1,
        'type': ftype,
        'rows': rows,
        'shift': shift,
        'shift_conf': conf,
        'h_lines': hl,
        'v_lines': vl,
        'size': [img.shape[1], img.shape[0]],
    }
    if ftype == '中型':
        arrange = detect_arrange_grid(gray, rows) if ocr_arrange else None
        result['arrange'] = arrange
        cols = detect_mid_columns(vl)
        if cols:
            result['mid_layout'] = {
                'cols': cols,
                'bands': [mid_band_layout(y0, y1, cols) for y0, y1 in rows],
            }
        if ocr:
            result['auto_fields'] = ocr_auto_fields(pdf_path, page_index, rows, arrange, result.get('mid_layout'))
    return result


def filename_date(pdf_name):
    """1150729.pdf → (ROC=1150729, ISO=2026-07-29, 顯示=115.07.29)"""
    m = re.match(r'(\d{3})(\d{2})(\d{2})', pdf_name)
    if not m:
        return None, None, None
    roc, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    iso = '%04d-%02d-%02d' % (roc + 1911, mm, dd)
    disp = '%d.%02d.%02d' % (roc, mm, dd)
    return '%03d%02d%02d' % (roc, mm, dd), iso, disp


def analyze_pdf(pdf_path, ocr=True):
    name = os.path.basename(pdf_path)
    roc, iso, disp = filename_date(name)
    pages = st.render_pages(pdf_path, 200)
    result = {'pdf': name, 'date_roc': roc, 'date_iso': iso, 'date_disp': disp, 'pages': []}
    for i in range(len(pages)):
        result['pages'].append(page_analysis(pdf_path, i, ocr=ocr))
    return result


if __name__ == '__main__':
    import json
    out = []
    for pdf in ['1150721.pdf', '1150724.pdf', '1150729.pdf', '1150702.pdf']:
        a = analyze_pdf(pdf)
        out.append('== %s %s' % (a['pdf'], a['date_iso']))
        for p in a['pages']:
            out.append('   p%d %s rows=%d shift=%s conf=%d' %
                       (p['page'], p['type'], len(p['rows']), p['shift'], p['shift_conf']))
    with open(os.path.join(DEBUG, 'diag_analysis.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('done')
