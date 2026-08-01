"""把指定頁指定列的格子區塊存成標註圖(寫上格子編號),供人工檢視"""
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st


def dump_row(pdf, page_index, row_idx, v_lines, outdir="debug"):
    img = st.render_pages(pdf, 200)[page_index]
    h_lines = st.find_lines(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))[0]
    y0, y1 = h_lines[row_idx], h_lines[row_idx + 1]
    for i in range(len(v_lines) - 1):
        x0, x1 = v_lines[i], v_lines[i + 1]
        w = x1 - x0
        if w < 30:
            continue
        cell = img[y0:y1, x0:x1]
        up = cv2.resize(cell, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        cv2.putText(up, f"S{i}", (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.imwrite(os.path.join(outdir, f"row_{pdf}_p{page_index+1}_r{row_idx}_slot{i}.png"), up)
    full = img[y0:y1, :]
    cv2.imwrite(os.path.join(outdir, f"row_{pdf}_p{page_index+1}_r{row_idx}_full.png"), full)
    print(f"page{page_index+1} row{row_idx} y={y0}..{y1} slots saved")


if __name__ == "__main__":
    pdf = sys.argv[1]
    page = int(sys.argv[2]) - 1
    row = int(sys.argv[3])
    img = st.render_pages(pdf, 200)[page]
    h_lines, v_lines, *_ = st.find_lines(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    dump_row(pdf, page, row, v_lines)
