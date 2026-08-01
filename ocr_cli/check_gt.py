# -*- coding: utf-8 -*-
import csv, glob, os

for day in ['115.07.24', '115.07.29', '115.07.21', '115.07.02']:
    p = glob.glob(os.path.join('csv', day + '*.csv'))
    if not p:
        print(day, 'NO CSV')
        continue
    with open(p[0], encoding='utf-8-sig') as f:
        r = csv.DictReader(f)
        rows = [(x['檔案日期'], x['類型'], x['時段'], x['番數']) for x in r]
    print(day, '->', rows)
