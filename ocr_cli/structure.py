"""表格結構定位:PDF → 頁面影像 → 水平/垂直線 → 格子矩陣"""
import argparse
import json
import os

import cv2
import fitz
import numpy as np


def render_pages(pdf_path, dpi=200):
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        zoom = dpi / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        pages.append(img)
    return pages


def find_lines(gray):
    binv = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    h, w = gray.shape

    kh = max(3, w // 15)
    kline_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kh, 1))
    horiz = cv2.morphologyEx(binv, cv2.MORPH_OPEN, kline_h)

    kv = max(3, h // 15)
    kline_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv))
    vert = cv2.morphologyEx(binv, cv2.MORPH_OPEN, kline_v)

    def row_runs(mask):
        sums = mask.sum(axis=1) / 255
        ys = np.where(sums > w * 0.25)[0]
        return cluster(ys, 8)

    def col_runs(mask):
        sums = mask.sum(axis=0) / 255
        xs = np.where(sums > h * 0.25)[0]
        return cluster(xs, 8)

    h_lines = row_runs(horiz)
    v_lines = col_runs(vert)
    return h_lines, v_lines, binv, horiz, vert


def cluster(idx, gap):
    if len(idx) == 0:
        return []
    out = []
    start = prev = idx[0]
    for v in idx[1:]:
        if v - prev > gap:
            out.append(int(round((start + prev) / 2)))
            start = v
        prev = v
    out.append(int(round((start + prev) / 2)))
    return out


def build_grid(h_lines, v_lines, tol=15):
    table = []
    for i, y in enumerate(h_lines[:-1]):
        row = []
        for j, x in enumerate(v_lines[:-1]):
            row.append([x, y, v_lines[j + 1] - x, h_lines[i + 1] - y])
        table.append(row)
    return table


def analyze(pdf_path, dpi=200, outdir=None):
    pages = render_pages(pdf_path, dpi)
    result = {"pdf": os.path.basename(pdf_path), "dpi": dpi, "pages": []}
    for pi, img in enumerate(pages):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h_lines, v_lines, binv, horiz, vert = find_lines(gray)
        grid = build_grid(h_lines, v_lines)
        result["pages"].append(
            {
                "index": pi + 1,
                "size": [img.shape[1], img.shape[0]],
                "h_lines": h_lines,
                "v_lines": v_lines,
                "rows": len(grid),
                "cols": len(grid[0]) if grid else 0,
            }
        )
        if outdir:
            annot = img.copy()
            for y in h_lines:
                cv2.line(annot, (0, y), (img.shape[1], y), (0, 0, 255), 2)
            for x in v_lines:
                cv2.line(annot, (x, 0), (x, img.shape[0]), (0, 255, 0), 2)
            cv2.imwrite(os.path.join(outdir, f"{os.path.basename(pdf_path)}_{pi+1}_grid.png"), annot)
            cv2.imwrite(os.path.join(outdir, f"{os.path.basename(pdf_path)}_{pi+1}_raw.png"), img)
    return result


def main():
    ap = argparse.ArgumentParser(description="偵測掃描表格的水平/垂直線,輸出格子結構")
    ap.add_argument("pdf", help="PDF 路徑")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--outdir", default="debug")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    result = analyze(args.pdf, args.dpi, args.outdir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
