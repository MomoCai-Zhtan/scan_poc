"""偵測表格類型(小型/中型)與上午/下午勾選框"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st


def detect_checkboxes(img, y_band=(180, 240)):
    """在表頭 y_band 內找兩個 ~30px 方框,回傳 (上午box, 下午box) 或 (None, None)"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    y0, y1 = y_band
    band = gray[y0:y1, :]
    _, bw = cv2.threshold(band, 130, 255, cv2.THRESH_BINARY_INV)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    boxes = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if 15 <= w <= 60 and 15 <= h <= 60 and 0.5 <= area / (w * h) <= 0.95:
            boxes.append((x + w // 2, y0 + y + h // 2, x, y0 + y, w, h))
    boxes.sort()
    if len(boxes) < 2:
        return None, None
    left, right = boxes[0], boxes[-1]
    return left, right


def box_checked(img, box):
    cx, cy, x, y, w, h = box
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    inner = gray[y + 3 : y + h - 3, x + 3 : x + w - 3]
    dark = (inner < 130).sum()
    return dark, inner.size


def classify_form(h_lines, v_lines):
    """依列高/欄數分類頁面型別"""
    gaps = [b - a for a, b in zip(h_lines[:-1], h_lines[1:])]
    med = np.median(gaps) if gaps else 0
    if len(v_lines) >= 18:
        return "小型"
    if len(v_lines) >= 14:
        return "中型"
    return "未知"


def page_meta(pdf, page_index):
    img = st.render_pages(pdf, 200)[page_index]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h_lines, v_lines, *_ = st.find_lines(gray)
    ftype = classify_form(h_lines, v_lines)
    am, pm = detect_checkboxes(img)
    checked = None
    if am and pm:
        da, sa = box_checked(img, am)
        dp, sp = box_checked(img, pm)
        checked = "上午" if da > dp else "下午"
    else:
        da = dp = sa = sp = 0
    return {
        "type": ftype,
        "rows": len(h_lines) - 1 if h_lines else 0,
        "h_lines": h_lines,
        "v_lines": v_lines,
        "check": checked,
        "am_dark": da,
        "pm_dark": dp,
        "am_box": am,
        "pm_box": pm,
    }


if __name__ == "__main__":
    for pdf in ["1150702.pdf", "1150721.pdf", "1150724.pdf", "1150729.pdf"]:
        doc = st.render_pages(pdf, 200)
        print(f"== {pdf} ==")
        for i in range(len(doc)):
            m = page_meta(pdf, i)
            print(f"  p{i+1}: type={m['type']} rows={m['rows']} check={m['check']} "
                  f"am_dark={m['am_dark']} pm_dark={m['pm_dark']} am_box={m['am_box']} pm_box={m['pm_box']}")
