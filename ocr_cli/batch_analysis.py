# -*- coding: utf-8 -*-
"""全部 PDF 批次分析"""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis

out = []
pdfs = sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '*.pdf')))
for pdf in pdfs:
    try:
        a = analysis.analyze_pdf(pdf)
    except Exception as e:
        out.append('%s ERROR %s' % (os.path.basename(pdf), e))
        continue
    parts = ['== %s %s' % (a['pdf'], a['date_iso'])]
    for p in a['pages']:
        parts.append('   p%d %s rows=%d shift=%s' % (p['page'], p['type'], len(p['rows']), p['shift']))
    out.append('\n'.join(parts))
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'debug', 'batch_analysis.txt'),
          'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done %d pdfs' % len(pdfs))
