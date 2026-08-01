# -*- coding: utf-8 -*-
"""每頁偵測列數 vs CSV 實際列數"""
import csv, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

out = []
for pdf in sorted(glob.glob(os.path.join(ROOT, '*.pdf'))):
    name = os.path.basename(pdf)
    a = analysis.analyze_pdf(pdf)
    if not a['date_roc']:
        continue
    csvs = glob.glob(os.path.join(ROOT, 'csv', a['date_disp'] + '*.csv'))
    if not csvs:
        continue
    with open(csvs[0], encoding='utf-8-sig') as f:
        gt = list(csv.DictReader(f))
    # 依 (類型, 時段) 分組
    groups = []
    cur = None
    for x in gt:
        key = (x['類型'], x['時段'])
        if cur != key:
            cur = key
            groups.append([key, 0])
        groups[-1][1] += 1
    parts = ['== %s' % name]
    for i, p in enumerate(a['pages']):
        g = groups[i] if i < len(groups) else None
        det = len(p['rows'])
        gd = '%s/%s → %d' % (g[0][0], g[0][1], g[1]) if g else '?'
        diff = (det - g[1]) if g else '?'
        parts.append('   p%d %-4s det=%d | gt=%s | diff=%s' % (p['page'], p['type'], det, gd, diff))
    out.append('\n'.join(parts))
with open(os.path.join(ROOT, 'debug', 'rows_vs_gt.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')
