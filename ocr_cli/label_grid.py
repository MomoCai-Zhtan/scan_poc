"""產生標註格子編號的除錯圖,方便人工確認版面對應"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st


def label_grid(pdf_path, page_index, outdir="debug", dpi=200):
    os.makedirs(outdir, exist_ok=True)
    img = st.render_pages(pdf_path, dpi)[page_index]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h_lines, v_lines, binv, horiz, vert = st.find_lines(gray)
    annot = img.copy()
    step = max(1, img.shape[0] // 1200)
    annot = cv2.resize(annot, (annot.shape[1] // step, annot.shape[0] // step), interpolation=cv2.INTER_AREA)
    scale = step
    for y in h_lines:
        cv2.line(annot, (0, y // scale), (annot.shape[1], y // scale), (0, 0, 255), 1)
    for x in v_lines:
        cv2.line(annot, (x // scale, 0), (x // scale, annot.shape[0]), (0, 255, 0), 1)
    for i, y in enumerate(h_lines):
        cv2.putText(annot, f"R{i}", (5, y // scale + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)
    for j, x in enumerate(v_lines):
        cv2.putText(annot, f"C{j}", (x // scale + 1, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)
    out = os.path.join(outdir, f"{os.path.basename(pdf_path)}_p{page_index+1}_labeled.png")
    cv2.imwrite(out, annot)
    print("saved:", out)


if __name__ == "__main__":
    pdf = sys.argv[1]
    for pi in range(3):
        try:
            label_grid(pdf, pi)
        except IndexError:
            break
