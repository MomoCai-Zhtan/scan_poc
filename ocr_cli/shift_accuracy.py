# -*- coding: utf-8 -*-
"""比對所有 PDF 的時段偵測 vs CSV ground truth"""
import csv, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def gt_shifts(day):
    """回傳 {page_index: shift} 依 CSV 時段順序組合"""
    csvs = glob.glob(os.path.join(ROOT, 'csv', day + '*.csv'))
    if not csvs:
        return None
    with open(csvs[0], encoding='utf-8-sig') as f:
        r = list(csv.DictReader(f))
    # 依類型與時段分組
    seq = []
    cur = None
    for x in r:
        key = (x['類型'], x['時段'])
        if cur != key:
            cur = key
            seq.append(key)
    return seq

out = []
total = good = 0
for pdf in sorted(glob.glob(os.path.join(ROOT, '*.pdf'))):
    name = os.path.basename(pdf)
    a = analysis.analyze_pdf(pdf)
    g = gt_shifts(a['date_disp']) if a['date_disp'] else None
    if g is None:
        out.append('%s (無 CSV)' % name)
        continue
    parts = ['== %s' % name]
    if len(g) != len(a['pages']):
        parts.append('   [CSV頁組數 %d != PDF頁數 %d]' % (len(g), len(a['pages'])))
    for i, p in enumerate(a['pages']):
        gt = g[i][1] if i < len(g) else '?'
        det = p['shift'] or '?'
        ok = (gt == det)
        total += 1
        if ok: good += 1
        parts.append('   p%d %s det=%s gt=%s %s' % (p['page'], p['type'], det, gt, 'OK' if ok else 'X'))
    out.append('\n'.join(parts))
out.append('=== 時段準確: %d/%d' % (good, total))
with open(os.path.join(ROOT, 'debug', 'shift_accuracy.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')
