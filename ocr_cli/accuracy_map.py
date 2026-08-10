# -*- coding: utf-8 -*-
"""Accuracy map: pre-computed OCR accuracy stats per PDF from GT baseline.

Usage:
    python accuracy_map.py --pdf 1150729.pdf
    python accuracy_map.py --save
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_baseline as vb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(ROOT, 'csv')
CACHE_PATH = os.path.join(ROOT, 'scan_entry', 'data', 'accuracy_map.json')


def compute_one(pdf):
    summary = {'tot': 0, 'ok': 0, 'errs': [], 'warn': [], 'per_field': {},
               'per_field_totals': {}, 'per_field_errors': {}}
    vb.verify_pdf(pdf, do_arrange=False, perband=False, summary=summary)
    tot, ok = summary['tot'], summary['ok']
    acc = 100.0 * ok / tot if tot else 0.0
    
    # Compute per-field accuracy
    per_field_acc = {}
    for key, total in summary['per_field_totals'].items():
        errors = summary['per_field_errors'].get(key, 0)
        per_field_acc[key] = {
            'total': total,
            'correct': total - errors,
            'accuracy': round(100.0 * (total - errors) / total, 1) if total else 0
        }
    
    return {
        'pdf': pdf,
        'total': tot,
        'correct': ok,
        'accuracy': round(acc, 1),
        'errors': len(summary['errs']),
        'warnings': len(summary['warn']),
        'per_field': per_field_acc,
    }


def compute_all():
    pdfs = sorted(f for f in os.listdir(ROOT)
                  if f.endswith('.pdf') and f.startswith('11507')
                  and os.path.exists(os.path.join(CSV_DIR, vb.A.filename_date(f)[2] + '.csv')))
    out = {}
    for pdf in pdfs:
        try:
            out[pdf.replace('.pdf', '')] = compute_one(pdf)
        except Exception as e:
            print('ERROR %s: %s' % (pdf, e), file=sys.stderr)
    return out


def load():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', help='compute accuracy for one PDF')
    parser.add_argument('--save', action='store_true', help='save all to cache')
    args = parser.parse_args()

    if args.pdf:
        print(json.dumps(compute_one(args.pdf), ensure_ascii=False))
    elif args.save:
        out = compute_all()
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('Saved', len(out), 'entries to', CACHE_PATH)
    else:
        cached = load()
        if cached:
            print(json.dumps(cached, ensure_ascii=False, indent=2))
        else:
            print('No cache. Run with --save first.')


if __name__ == '__main__':
    main()
