# -*- coding: utf-8 -*-
"""EasyOCR 基準測試:中型頁格子裁切 → 辨識 → 對照 GT 算準確率。"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
import numpy as np

import analysis as an
import structure as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    if s is None:
        return ''
    s = str(s).strip()
    s = s.replace('，', ',').replace('．', '.')
    out = []
    for ch in s:
        c = ord(ch)
        if 0xFF01 <= c <= 0xFF5E:
            ch = chr(c - 0xFEE0)
        out.append(ch)
    return ''.join(out)


def digits(s):
    return re.sub(r'\D', '', norm(s))


def load_gt(pdf):
    roc = pdf.replace('.pdf', '')
    p = os.path.join(ROOT, 'csv', '%s.%s.%s.csv' % (roc[:3], roc[3:5], roc[5:7]))
    rows = []
    with open(p, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['類型'] == '中型':
                rows.append(r)
    return rows


def cut(gray, y0, y1, x0, x1, pad=4):
    y0 = max(0, y0 + pad)
    y1 = min(gray.shape[0], y1 - pad)
    x0 = max(0, x0 + pad)
    x1 = min(gray.shape[1], x1 - pad)
    if x1 <= x0 or y1 <= y0:
        return None
    crop = gray[y0:y1, x0:x1]
    h, w = crop.shape
    if max(h, w) < 40:
        return None
    scale = max(2.0, 120.0 / h)
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return crop


CELLS = [
    ('序', 89, 147, 'top', '序'),
    ('品項', 147, 252, 'top', '品項'),
    ('模具1', 252, 324, 'top', '轉位1'),
    ('模具2', 324, 390, 'top', '轉位2'),
    ('模具3', 390, 455, 'top', '轉位3'),
    ('模具4', 455, 521, 'top', '轉位4'),
    ('加料轉速', 521, 587, 'top', '加料轉速'),
    ('加料時間', 521, 587, 'bot', '加料時間'),
    ('慢速轉速', 587, 660, 'top', '慢速轉速'),
    ('慢速時間', 587, 660, 'bot', '慢速時間'),
    ('中速轉速', 660, 732, 'top', '中速轉速'),
    ('中速時間', 660, 732, 'bot', '中速時間'),
    ('高速轉速', 732, 804, 'top', '高速轉速'),
    ('高速時間', 732, 804, 'bot', '高速時間'),
    ('蒸養池', 876, 958, 'full', '蒸養池'),
    ('入池時間', 1248, 1320, 'full', '入池時間'),
]


def main(pdf='1150729.pdf'):
    gt = load_gt(pdf)
    print('GT 中型列數:', len(gt))
    imgs = st.render_pages(pdf, 200)
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    correct = 0
    total = 0
    misses = []
    for pi in range(len(imgs)):
        res = an.page_analysis(pdf, pi)
        if res['type'] != '中型':
            continue
        shift = res['shift']
        bands = res['rows']
        print('== p%d 時段=%s bands=%d' % (pi + 1, shift, len(bands)))
        gtshift = [r for r in gt if r['時段'] == shift]
        gtshift.sort(key=lambda r: int(r['番數']))
        gray = cv2.cvtColor(imgs[pi], cv2.COLOR_BGR2GRAY)
        for bi, (y0, y1) in enumerate(bands):
            if bi >= len(gtshift):
                continue
            g = gtshift[bi]
            mid = y0 + (y1 - y0) // 2
            print('  番%d 序GT=%s' % (bi + 1, g['序']))
            for name, x0, x1, half, gk in CELLS:
                yy0, yy1 = y0, y1
                if half == 'top':
                    yy1 = mid
                elif half == 'bot':
                    yy0 = mid
                crop = cut(gray, yy0, yy1, x0, x1)
                if crop is None:
                    continue
                ocr = reader.readtext(crop, detail=0, paragraph=False)
                text = ' '.join(ocr)
                gtval = norm(g.get(gk, ''))
                exp = ''
                if gk == '序':
                    exp = gtval.replace(',', '')
                elif gk == '品項':
                    exp = re.sub(r'\D', '', gtval)
                else:
                    exp = digits(gtval)
                match = digits(text) == exp
                correct += match
                total += 1
                flag = 'OK ' if match else 'MISS'
                print('    [%s] %s GT=%-8s OCR=%s' % (flag, name, gtval, text))
                if not match:
                    misses.append((pdf, pi + 1, bi + 1, name, gtval, text))
    print()
    print('== 總計: %d/%d 正確 = %.1f%%' % (correct, total, 100.0 * correct / total))
    for m in misses:
        print('  MISS', m)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '1150729.pdf')
