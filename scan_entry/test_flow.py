# -*- coding: utf-8 -*-
"""模擬 UI 完整流程:依 collectRows 順序(頁序→番序)組 GT 值 → 匯出 → 逐位元比對"""
import csv, glob, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def ui_order_rows(gt, date_iso):
    """模擬 UI 輸出順序:分組(類型,時段)依頁序,組內依番序。回傳 rows dict 列表。"""
    groups = []
    for x in gt:
        key = (x['類型'], x['時段'])
        if not groups or groups[-1]['key'] != key:
            groups.append({'key': key, 'rows': []})
        groups[-1]['rows'].append(x)
    rows = []
    for g in groups:
        for x in g['rows']:
            r = dict(x)
            r['日期'] = date_iso
            rows.append(r)
    return rows

for day in ['115.07.02', '115.07.06', '115.07.14', '115.07.29']:
    for p in glob.glob(os.path.join(ROOT, 'csv', day + '.csv')):
        with open(p, encoding='utf-8-sig') as f:
            gt = list(csv.DictReader(f))
        date_iso = '%s-%s-%s' % (int(day[0:3]) + 1911, day[4:6], day[7:9])
        rows = ui_order_rows(gt, date_iso)
        roc = day.replace('.', '')
        body = json.dumps({'pdf': roc + '.pdf', 'date_iso': date_iso, 'date_roc': roc,
                           'rows': rows}).encode('utf-8')
        req = urllib.request.Request('http://127.0.0.1:5000/export', data=body,
                                     headers={'Content-Type': 'application/json'})
        print(urllib.request.urlopen(req).read().decode('utf-8'))
        with open(p, encoding='utf-8-sig') as f:
            orig = f.read()
        with open(p, encoding='utf-8-sig') as f:
            new = f.read()
        print('%s: %s' % (day, 'IDENTICAL' if orig == new else 'DIFFERS'))
