"""實驗:對指定列/指定欄位 OCR 所有格子,輸出與 CSV 比對"""
import csv
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st

try:
    sys.stdout.reconfigure(errors="replace", encoding="utf-8")
except Exception:
    pass

TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tessdata")

os.environ["TESSDATA_PREFIX"] = TESSDATA
import pytesseract

pytesseract.pytesseract.tesseract_cmd = TESS


def ocr_cell(img, x, y, w, h, psm=7):
    cell = img[y : y + h, x : x + w]
    up = cv2.resize(cell, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(g, 150, 255, cv2.THRESH_BINARY)
    cfg = f"--psm {psm} -c tessedit_char_whitelist=0123456789"
    try:
        t = pytesseract.image_to_string(bw, config=cfg).strip()
    except Exception:
        t = ""
    return t


def main(pdf, page_index, row_idx, v_lines, out=None):
    img = st.render_pages(pdf, 200)[page_index]
    h = img.shape[0]
    tops = st.find_lines(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))[0]
    y0 = tops[row_idx]
    y1 = tops[row_idx + 1]
    cells = []
    for i in range(len(v_lines) - 1):
        x0, x1 = v_lines[i], v_lines[i + 1]
        if x1 - x0 < 30:
            continue
        cells.append((i, x0, y0, x1 - x0, y1 - y0))
    print(f"page{page_index+1} row{row_idx} y={y0}..{y1}")
    for i, x, yy, w, hh in cells:
        t = ocr_cell(img, x, yy, w, hh)
        print(f"  slot{i:2d} x={x:4d} w={w:3d}: {t!r}")


if __name__ == "__main__":
    pdf = sys.argv[1]
    page = int(sys.argv[2]) - 1
    row = int(sys.argv[3])
    img = st.render_pages(pdf, 200)[page]
    h_lines, v_lines, *_ = st.find_lines(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    main(pdf, page, row, v_lines)
