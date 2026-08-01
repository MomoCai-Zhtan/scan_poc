# -*- coding: utf-8 -*-
"""測試 /export:用既有 CSV 資料走 API,比對匯出"""
import csv, io, json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, 'csv', '115.07.29.csv')

with open(CSV_PATH, encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    rows = [dict(x) for x in r]

body = json.dumps({
    'pdf': '1150729.pdf',
    'date_iso': '2026-07-29',
    'date_roc': '1150729',
    'rows': rows,
}).encode('utf-8')

req = urllib.request.Request('http://127.0.0.1:5000/export', data=body,
                             headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
print(resp.read().decode('utf-8'))

# 比對
out_path = os.path.join(ROOT, 'csv', '115.07.29.csv')
def read(p):
    with open(p, encoding='utf-8-sig') as f:
        return f.read()
orig = read(CSV_PATH)
new = read(out_path)
print('IDENTICAL' if orig == new else 'DIFFERS')
if orig != new:
    a = orig.splitlines()
    b = new.splitlines()
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            print('line', i, '\n orig:', x[:200], '\n new :', y[:200])
