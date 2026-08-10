# -*- coding: utf-8 -*-
"""Baseline: compare hybrid OCR (page_analysis auto_fields) vs GT CSV for 中型/小型 pages.

Usage:
    python verify_baseline.py [--arrange] [--all] [--json] [--threshold N] [pdf1.pdf pdf2.pdf ...]
        --arrange    also OCR C13 circled digits / 排列 and compare vs GT 排列
                     (default: core fields only — fewer API calls)
        --all        run all 11507*.pdf with matching GT CSV (ignores positional args)
        --json       output JSON to stdout (for CI consumption)
        --threshold  fail if accuracy < N% (default: 75)
        no pdf args  → same as --all (backward compatible)

Output: debug/baseline_<date>.md + console summary.
"""
import os
import re
import sys
import csv
import io
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis as A

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(ROOT, 'csv')
DEBUG = os.path.join(ROOT, 'debug')


def read_gt_mid(csv_path):
    """Return {'上午': [rows...], '下午': [...]} filtered to 中型 rows."""
    with io.open(csv_path, encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    out = {}
    for r in rows[1:]:
        if len(r) < 39 or r[1] != '中型':
            continue
        out.setdefault(r[5], []).append(r)
    return out


def read_gt_small(csv_path):
    """Return list of 小型 rows in 序 order."""
    with io.open(csv_path, encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    return [r for r in rows[1:] if len(r) >= 39 and r[1] == '小型']


def norm(s):
    return re.sub(r'\s+', '', s or '').strip()


def compare_band(gt, b, do_arrange):
    """Compare one GT row vs one OCR band dict.
    Returns (results, total, correct). results: (field, idx, gt, ocr, ok)."""
    results = []
    total = correct = 0

    def acc(ok, field, idx, g, o):
        nonlocal total, correct
        total += 1
        if ok:
            correct += 1
        results.append((field, idx, g, o, ok))

    gv, ov = norm(gt[4]), norm(b.get('item'))
    acc(gv == ov, 'item', 0, gt[4], b.get('item'))

    molds = b.get('molds') if isinstance(b.get('molds'), list) else []
    for i in range(4):
        g = norm(gt[8 + i])
        if not g:
            continue
        o = norm(molds[i]) if i < len(molds) else ''
        acc(g == o, 'molds', i, g, o)

    bc = b.get('centrifuge') if isinstance(b.get('centrifuge'), (list, tuple)) else ('', '')
    for i in range(2):
        g = norm(gt[14 + i])
        if not g:
            continue
        o = norm(bc[i]) if i < len(bc) else ''
        acc(g == o, 'cent', i, g, o)

    sp = b.get('speeds') or []
    for i in range(4):
        g = norm(gt[16 + i])
        if not g:
            continue
        o = norm(sp[i]) if i < len(sp) else ''
        acc(g == o, 'speeds', i, g, o)

    tm = b.get('speed_times') or []
    for i in range(4):
        g = norm(gt[20 + i])
        if not g:
            continue
        o = norm(tm[i]) if i < len(tm) else ''
        acc(g == o, 'times', i, g, o)

    g = norm(gt[24])
    if g:
        acc(g == norm(b.get('steam_pool')), 'pool', 0, g, b.get('steam_pool'))

    if do_arrange:
        arr = list(b.get('arrange') or [])
        for i in range(4):
            g = norm(gt[33 + i])
            if not g:
                continue
            o = norm(arr[i]) if i < len(arr) else ''
            acc(g == o, 'arrange', i, g, o)
    return results, total, correct


def compare_band_small(gt, b, do_arrange):
    """Compare one GT 小型 row vs one OCR small band dict.
    GT cols: 4=品項 8-13=轉位1-6 14-15=離心 16-19=轉速 20-23=時間
             24=池 25=入池 26-28=溫度 29-31=階段 32=位置 33-38=排列1-6."""
    results = []
    total = correct = 0

    def acc(ok, field, idx, g, o):
        nonlocal total, correct
        total += 1
        if ok:
            correct += 1
        results.append((field, idx, g, o, ok))

    gv, ov = norm(gt[4]), norm(b.get('item'))
    acc(gv == ov, 'item', 0, gt[4], b.get('item'))

    molds = b.get('molds') if isinstance(b.get('molds'), list) else []
    for i in range(6):
        g = norm(gt[8 + i])
        if not g:
            continue
        o = norm(molds[i]) if i < len(molds) else ''
        acc(g == o, 'molds', i, g, o)

    bc = b.get('centrifuge') if isinstance(b.get('centrifuge'), (list, tuple)) else ('', '')
    for i in range(2):
        g = norm(gt[14 + i])
        if not g:
            continue
        o = norm(bc[i]) if i < len(bc) else ''
        acc(g == o, 'cent', i, g, o)

    sp = b.get('speeds') or []
    for i in range(4):
        g = norm(gt[16 + i])
        if not g:
            continue
        o = norm(sp[i]) if i < len(sp) else ''
        acc(g == o, 'speeds', i, g, o)

    tm = b.get('speed_times') or []
    for i in range(4):
        g = norm(gt[20 + i])
        if not g:
            continue
        o = norm(tm[i]) if i < len(tm) else ''
        acc(g == o, 'times', i, g, o)

    g = norm(gt[24])
    if g:
        acc(g == norm(b.get('steam_pool')), 'pool', 0, g, b.get('steam_pool'))

    g = norm(gt[25])
    if g:
        acc(g == norm(b.get('pool_time')), 'pool_time', 0, g, b.get('pool_time'))

    temps = b.get('temps') or []
    for i in range(3):
        g = norm(gt[26 + i])
        if not g:
            continue
        o = norm(temps[i]) if i < len(temps) else ''
        acc(g == o, 'temps', i, g, o)

    stages = b.get('stages') or []
    for i in range(3):
        g = norm(gt[29 + i])
        if not g:
            continue
        o = norm(stages[i]) if i < len(stages) else ''
        acc(g == o, 'stages', i, g, o)

    if do_arrange:
        arr = list(b.get('arrange') or [])
        for i in range(6):
            g = norm(gt[33 + i])
            if not g:
                continue
            o = norm(arr[i]) if i < len(arr) else ''
            acc(g == o, 'arrange', i, g, o)
    return results, total, correct


def perband_auto_fields(pdf_path, page_index, rows):
    """Per-band OCR (band + header composite) for EVERY band — no full-page pass.
    Measures the ceiling of the per-band crop approach."""
    import ocrx
    bands = {}
    for bi, (y0, y1) in enumerate(rows):
        try:
            md = ocrx.ocr_band_with_header(pdf_path, page_index, y0, y1)
            if not md:
                continue
            parsed = ocrx.parse_mid_table(md)
            if parsed:
                bands[bi] = parsed.get(0, {})
        except Exception:
            continue
    return bands


def _track_field(summary, field, idx, is_ok):
    key = '%s[%d]' % (field, idx)
    summary['per_field_totals'][key] = summary['per_field_totals'].get(key, 0) + 1
    if not is_ok:
        summary['per_field_errors'][key] = summary['per_field_errors'].get(key, 0) + 1


def verify_pdf(pdf_name, do_arrange, perband, summary):
    roc, iso, disp = A.filename_date(pdf_name)
    csv_path = os.path.join(CSV_DIR, disp + '.csv')
    gt = read_gt_mid(csv_path) if os.path.exists(csv_path) else None
    gt_small = read_gt_small(csv_path) if os.path.exists(csv_path) else None
    pdf_path = os.path.join(ROOT, pdf_name)
    pages = A.st.render_pages(pdf_path, 200)
    used_shift = {}
    per_shift = {}
    small_done = False
    for i in range(len(pages)):
        p = A.page_analysis(pdf_path, i, ocr_arrange=do_arrange)
        if p['type'] == '小型':
            if small_done:
                continue
            small_done = True
            if not gt_small:
                summary['warn'].append('%s p%d 小型: 無 GT' % (pdf_name, p['page']))
                continue
            bands = p.get('auto_fields') or {}
            rows = list(bands.items())
            per_shift['小型'] = rows
            for bi, b in rows:
                if bi >= len(gt_small):
                    summary['warn'].append('%s 小型 番%d: GT 無對應列' % (pdf_name, bi + 1))
                    continue
                res, tot, ok = compare_band_small(gt_small[bi], b, do_arrange)
                summary['tot'] += tot
                summary['ok'] += ok
                for field, idx, g, o, is_ok in res:
                    _track_field(summary, field, idx, is_ok)
                    if not is_ok:
                        summary['errs'].append(
                            '%s 小型 番%d %s[%d] GT=%r OCR=%r' % (pdf_name, bi + 1, field, idx, g, o))
            continue
        if p['type'] != '中型':
            continue
        shift = p['shift']
        if not gt or shift not in gt:
            summary['warn'].append('%s p%d %s: 無 GT' % (pdf_name, p['page'], shift))
            continue
        if shift in used_shift:
            summary['warn'].append('%s p%d: 重複 %s 頁' % (pdf_name, p['page'], shift))
            continue
        used_shift[shift] = p
        gt_rows = gt[shift]
        bands = perband_auto_fields(pdf_path, i, p['rows']) if perband else (p.get('auto_fields') or {})
        rows = list(bands.items())
        per_shift[shift] = rows
        for i, (bi, b) in enumerate(rows):
            if i >= len(gt_rows):
                summary['warn'].append('%s %s 番%d: GT 無對應列' % (pdf_name, shift, i + 1))
                continue
            res, tot, ok = compare_band(gt_rows[i], b, do_arrange)
            summary['tot'] += tot
            summary['ok'] += ok
            for field, idx, g, o, is_ok in res:
                _track_field(summary, field, idx, is_ok)
                if not is_ok:
                    summary['errs'].append(
                        '%s %s 番%d %s[%d] GT=%r OCR=%r' % (pdf_name, shift, i + 1, field, idx, g, o))
    return per_shift


def main():
    args = sys.argv[1:]
    do_arrange = '--arrange' in args
    perband = '--perband' in args
    do_all = '--all' in args
    do_json = '--json' in args
    threshold = 75.0
    if '--threshold' in args:
        try:
            ti = args.index('--threshold')
            threshold = float(args[ti + 1])
        except (IndexError, ValueError):
            threshold = 75.0
    pdfs = [a for a in args if a.endswith('.pdf') and not a.startswith('--')]
    if do_all or not pdfs:
        pdfs = sorted(f for f in os.listdir(ROOT)
                      if re.match(r'11507\d{2}\.pdf$', f)
                      and os.path.exists(os.path.join(CSV_DIR,
                          A.filename_date(f)[2] + '.csv')))

    summary = {'tot': 0, 'ok': 0, 'errs': [], 'warn': [], 'per_field': {}, 'per_field_totals': {}, 'per_field_errors': {}}
    for pdf in pdfs:
        verify_pdf(pdf, do_arrange, perband, summary)

    tot, ok = summary['tot'], summary['ok']
    acc = 100.0 * ok / tot if tot else 0.0
    mode = ('每番' if perband else '整頁')
    failed = acc < threshold

    lines = ['# 混合 OCR 基線 (%s%s)' % (mode, ' + 排列' if do_arrange else ''),
             '',
             'PDF 數: %d | 比較欄位: %d | 正確: %d | 準確率: %.1f%% | threshold: %.1f%%' % (
                 len(pdfs), tot, ok, acc, threshold),
             '']
    import collections
    err_cnt = collections.Counter()
    for e in summary['errs']:
        m = re.search(r'(item|molds|cent|speeds|times|pool|pool_time|temps|stages|arrange)\[(\d)\]', e)
        if m:
            err_cnt[m.group(1) + '[' + m.group(2) + ']'] += 1
    lines.append('## 錯誤分佈')
    lines.append('')
    for k in sorted(err_cnt):
        lines.append('- %s: %d' % (k, err_cnt[k]))
    lines.append('')
    lines.append('## 逐欄錯誤')
    lines.append('')
    lines.extend('- ' + e for e in summary['errs'])
    lines.append('')
    if summary['warn']:
        lines.append('## 警告')
        lines.append('')
        lines.extend('- ' + w for w in summary['warn'])
        lines.append('')

    os.makedirs(DEBUG, exist_ok=True)
    tag = A.filename_date(pdfs[0])[2] if pdfs else 'none'
    rep = os.path.join(DEBUG, 'baseline_%s.md' % tag)
    with io.open(rep, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    if do_json:
        out = {
            'ok': ok,
            'total': tot,
            'accuracy': round(acc, 2),
            'threshold': threshold,
            'failed': failed,
            'pdfs': len(pdfs),
            'per_field': dict(err_cnt),
            'errors': summary['errs'][:50],
            'warnings': summary['warn'][:20],
            'report': rep,
        }
        print(json.dumps(out, ensure_ascii=False))
    else:
        print('== 混合 OCR 基線 (含排列)' if do_arrange else '== 混合 OCR 基線 (核心欄位)')
        print('模式: %s' % mode)
        print('PDF=%d 欄位=%d 正確=%d 準確率=%.1f%% threshold=%.1f%%' % (
            len(pdfs), tot, ok, acc, threshold))
        for k in sorted(err_cnt):
            print('  %s: %d' % (k, err_cnt[k]))
        print('報告: %s' % rep)

    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
