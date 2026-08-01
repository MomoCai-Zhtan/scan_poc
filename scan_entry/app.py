# -*- coding: utf-8 -*-
"""掃描輸入工具 B MVP:PDF → 單頁聚焦 → 集合匯出 → 39欄 CSV"""
import csv
import glob
import logging
import os
import re
import sys
import json
import uuid
from datetime import datetime

import cv2
import flask
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, 'ocr_cli')
CSV_DIR = os.path.join(ROOT, 'csv')
CACHE = os.path.join(ROOT, 'scan_entry', 'cache')

sys.path.insert(0, OCR)
import analysis
import structure as st

app = flask.Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'scan-entry-secret-2026')

logger = logging.getLogger('scan_entry')
logger.setLevel(logging.INFO)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(_h)


def load_item_count():
    """品項 → 模具可生產量(支/模具) 對照表, 0 表示不固定需人工輸入。"""
    mapping = {}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'item_count.csv')
    if os.path.exists(path):
        with open(path, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                k = (row.get('品項') or '').strip()
                v = (row.get('模具可生產量') or '').strip()
                if k and v.isdigit():
                    mapping[k] = int(v)
    return mapping


ITEM_COUNT = load_item_count()

HEADER = ["日期", "類型", "番數", "序", "品項", "時段", "生產數量(支數)", "生產量修正(+/-量)",
          "轉位1", "轉位2", "轉位3", "轉位4", "轉位5", "轉位6",
          "離心開始", "離心結束", "加料轉速", "慢速轉速", "中速轉速", "高速轉速",
          "加料時間", "慢速時間", "中速時間", "高速時間",
          "蒸養池", "入池時間", "蒸養溫度1", "蒸養溫度2", "蒸養溫度3",
          "蒸養階段1", "蒸養階段2", "蒸養階段3", "位置",
          "排列1", "排列2", "排列3", "排列4", "排列5", "排列6"]

# In-memory collection: {session_id: [page_data, ...]}
COLLECTIONS = {}


def list_pdfs():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, '*.pdf')))


def get_pdf(name):
    name = os.path.basename(name)
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return None
    return path


@app.route('/')
def index():
    return flask.render_template('index.html', pdfs=list_pdfs(), header=HEADER, item_count=ITEM_COUNT)


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in flask.request.files:
        logger.warning('upload missing file')
        return flask.jsonify({'error': 'no file'}), 400
    f = flask.request.files['file']
    if not f.filename or not f.filename.lower().endswith('.pdf'):
        logger.warning('upload invalid file: %s', f.filename)
        return flask.jsonify({'error': 'invalid file'}), 400
    out = os.path.join(ROOT, f.filename)
    f.save(out)
    logger.info('upload saved: %s', f.filename)
    return flask.jsonify({'ok': True, 'name': f.filename})


@app.route('/api/pdf/<path:name>')
def api_pdf(name):
    """Full PDF analysis (structure only, no OCR). Returns all pages."""
    path = get_pdf(name)
    if not path:
        logger.warning('api_pdf not found: %s', name)
        return flask.jsonify({'error': 'not found'}), 404
    logger.info('api_pdf full: %s', name)
    return flask.jsonify(analysis.analyze_pdf(path))


@app.route('/api/pdf/<path:name>/<int:page>')
def api_pdf_page(name, page):
    """Single page analysis with OCR. Returns one page with auto_fields."""
    path = get_pdf(name)
    if not path:
        logger.warning('api_pdf_page not found: %s page=%d', name, page)
        return flask.jsonify({'error': 'not found'}), 404
    pages = st.render_pages(path, 200)
    if page < 1 or page > len(pages):
        logger.warning('api_pdf_page invalid page: %s page=%d (total=%d)', name, page, len(pages))
        return flask.jsonify({'error': 'invalid page'}), 404
    logger.info('api_pdf_page: %s page=%d', name, page)
    result = analysis.page_analysis(path, page - 1)
    return flask.jsonify(result)


@app.route('/api/pdf/<path:name>/<int:page>/ocr', methods=['POST'])
def api_pdf_page_ocr(name, page):
    """Re-trigger OCR for a single page (e.g., after user修正)."""
    path = get_pdf(name)
    if not path:
        logger.warning('api_pdf_page_ocr not found: %s page=%d', name, page)
        return flask.jsonify({'error': 'not found'}), 404
    pages = st.render_pages(path, 200)
    if page < 1 or page > len(pages):
        logger.warning('api_pdf_page_ocr invalid page: %s page=%d', name, page)
        return flask.jsonify({'error': 'invalid page'}), 404
    logger.info('api_pdf_page_ocr re-trigger: %s page=%d', name, page)
    result = analysis.page_analysis(path, page - 1)
    return flask.jsonify(result)


@app.route('/api/collection', methods=['GET'])
def get_collection():
    """Get current session's collection."""
    sid = flask.session.get('sid') or str(uuid.uuid4())
    flask.session['sid'] = sid
    coll = COLLECTIONS.get(sid, [])
    logger.info('collection GET sid=%s count=%d', sid[:8], len(coll))
    return flask.jsonify({'items': coll, 'count': len(coll)})


@app.route('/api/collection', methods=['POST'])
def add_to_collection():
    """Add current page's rows to collection."""
    sid = flask.session.get('sid') or str(uuid.uuid4())
    flask.session['sid'] = sid
    data = flask.request.get_json(force=True)
    page_data = {
        'pdf': data.get('pdf'),
        'page': data.get('page'),
        'date_iso': data.get('date_iso'),
        'date_roc': data.get('date_roc'),
        'date_disp': data.get('date_disp'),
        'type': data.get('type'),
        'rows': data.get('rows', []),
        'added_at': datetime.now().isoformat(),
    }
    if sid not in COLLECTIONS:
        COLLECTIONS[sid] = []
    COLLECTIONS[sid].append(page_data)
    logger.info('collection POST sid=%s page=%d rows=%d total=%d', sid[:8], page_data.get('page', 0), len(page_data.get('rows', [])), len(COLLECTIONS[sid]))
    return flask.jsonify({'ok': True, 'count': len(COLLECTIONS[sid])})


@app.route('/api/collection', methods=['DELETE'])
def clear_collection():
    """Clear collection."""
    sid = flask.session.get('sid')
    if sid and sid in COLLECTIONS:
        del COLLECTIONS[sid]
        logger.info('collection DELETE sid=%s', sid[:8])
    else:
        logger.warning('collection DELETE no session')
    return flask.jsonify({'ok': True})


@app.route('/img/<path:name>/<int:page>')
def img(name, page):
    path = get_pdf(name)
    if not path:
        return flask.abort(404)
    os.makedirs(CACHE, exist_ok=True)
    cache_png = os.path.join(CACHE, '%s_p%d.png' % (name.replace('.', '_'), page))
    if not os.path.exists(cache_png):
        pages = st.render_pages(path, 200)
        img = pages[page - 1]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hl, vl = analysis.find_lines_robust(gray)
        annot = img.copy()
        for y in hl:
            cv2.line(annot, (0, y), (annot.shape[1], y), (0, 0, 200), 2)
        for x in vl:
            cv2.line(annot, (x, 0), (x, annot.shape[0]), (0, 200, 0), 2)
        ok, buf = cv2.imencode('.png', annot)
        with open(cache_png, 'wb') as f:
            f.write(buf.tobytes())
    logger.debug('img cache=%s page=%d', cache_png, page)
    return flask.send_file(cache_png, mimetype='image/png')


@app.route('/crop/<path:name>/<int:page>/<int:band>/<area>')
def crop(name, page, band, area):
    path = get_pdf(name)
    if not path:
        return flask.abort(404)
    res = analysis.page_analysis(path, page - 1)
    if not res.get('mid_layout') or band >= len(res['mid_layout']['bands']):
        return flask.abort(404)
    layout = res['mid_layout']['bands'][band]
    img = st.render_pages(path, 200)[page - 1]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if area.startswith('c14_'):
        idx = int(area[4:])
        x, y, w, h = layout['c14_cells'][idx]
    elif area.startswith('c15_'):
        idx = int(area[4:])
        x, y, w, h = layout['c15_cells'][idx]
    elif area == 'centrifuge':
        x, y, w, h = layout['centrifuge']
    else:
        return flask.abort(404)

    y = min(y, gray.shape[0] - h)
    x = min(x, gray.shape[1] - w)
    crop_img = gray[y:y + h, x:x + w]
    crop_img = cv2.resize(crop_img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    crop_img = cv2.cvtColor(crop_img, cv2.COLOR_GRAY2BGR)
    ok, buf = cv2.imencode('.png', crop_img)
    resp = flask.Response(buf.tobytes(), mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-store'
    logger.debug('crop %s page=%d band=%d area=%s', name, page, band, area)
    return resp


@app.route('/export', methods=['POST'])
def export():
    data = flask.request.get_json(force=True)
    pdf = data.get('pdf')
    rows = data.get('rows', [])
    date_iso = data.get('date_iso', '')
    roc = data.get('date_roc', '')
    if not pdf or not roc:
        logger.warning('export missing pdf/date')
        return flask.jsonify({'error': 'missing pdf/date'}), 400
    name = '115.%s.%s.csv' % (roc[3:5], roc[5:7])
    out_path = os.path.join(CSV_DIR, name)
    os.makedirs(CSV_DIR, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            line = {}
            for k in HEADER:
                line[k] = (r.get(k) or '').strip()
            line['日期'] = date_iso
            w.writerow(line)
    logger.info('export %s rows=%d path=%s', pdf, len(rows), out_path)
    return flask.jsonify({'ok': True, 'path': out_path, 'rows': len(rows)})


if __name__ == '__main__':
    reload = os.environ.get('BTOOL_RELOAD') == '1'
    logger.info('starting scan_entry on :5000 reload=%s', reload)
    app.run(debug=reload, threaded=True, port=5000)
