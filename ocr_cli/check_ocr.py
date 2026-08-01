# -*- coding: utf-8 -*-
"""批次測試:OCR 表頭帶 → 找「囗」→ 定位勾選框 → 量內部墨跡"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG = os.path.join(ROOT, 'debug')


def ocr_band(pdf, pi, top=165, bottom=275, scale=3):
    """裁表頭帶,放大,OCR,回傳字詞 [(text, x, y, w, h)] (原始座標)"""
    img = st.render_pages(pdf, 200)[pi]
    crop = img[top:bottom, 0:900]
    up = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    p = os.path.join(DEBUG, '_band_ocr.png')
    cv2.imwrite(p, up)
    outp = os.path.join(DEBUG, '_band_ocr.txt')
    ps = os.path.join(ROOT, 'ocr_cli', 'win_ocr.ps1')
    subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps,
                    '-ImagePath', p, '-OutFile', outp], check=True)
    words = []
    with open(outp, encoding='utf-8') as f:
        for line in f:
            for m in re.finditer(r'\[(\S+)@(\d+),(\d+),(\d+),(\d+)\]', line):
                text, x, y, w, h = m.groups()
                words.append((text, int(x) // scale + 0, int(y) // scale + top,
                              int(w) // scale, int(h) // scale))
    return words


def interior_ink(gray, cx, cy, size=32):
    x0, y0 = cx - size // 2, cy - size // 2
    inner = gray[y0 + 6:y0 + size - 6, x0 + 6:x0 + size - 6]
    if inner.size == 0:
        return 0
    return int((inner < 130).sum())


if __name__ == '__main__':
    out = []
    for pdf in ['1150729.pdf', '1150724.pdf', '1150702.pdf', '1150721.pdf']:
        pages = st.render_pages(pdf, 200)
        for i in range(len(pages)):
            img = pages[i]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            words = ocr_band(pdf, i)
            out.append('== %s p%d' % (pdf, i + 1))
            for w in words:
                out.append('    %s@%s,%s' % (w[0], w[1], w[2]))
            boxes = [w for w in words if w[0] in ('囗', '口')]
            boxes.sort(key=lambda w: w[1])
            if len(boxes) >= 1:
                da = interior_ink(gray, boxes[0][1] + boxes[0][3] // 2, boxes[0][2] + boxes[0][4] // 2)
            else:
                da = 0
            if len(boxes) >= 2:
                dp = interior_ink(gray, boxes[1][1] + boxes[1][3] // 2, boxes[1][2] + boxes[1][4] // 2)
            else:
                dp = 0
            res = '上午' if da > dp else '下午'
            out.append('    boxes=%s da=%d dp=%d -> %s' % ([b[0:2] for b in boxes], da, dp, res))
    with open(os.path.join(DEBUG, 'diag_check_ocr.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('done')
