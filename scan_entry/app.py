# -*- coding: utf-8 -*-
"""掃描輸入工具 B MVP:PDF → 版面分析 → 網頁手動輸入 → 39欄 CSV"""
import csv
import glob
import os
import re
import sys

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
        return flask.jsonify({'error': 'no file'}), 400
    f = flask.request.files['file']
    if not f.filename or not f.filename.lower().endswith('.pdf'):
        return flask.jsonify({'error': 'invalid file'}), 400
    out = os.path.join(ROOT, f.filename)
    f.save(out)
    return flask.jsonify({'ok': True, 'name': f.filename})


@app.route('/api/pdf/<path:name>')
def api_pdf(name):
    path = get_pdf(name)
    if not path:
        return flask.jsonify({'error': 'not found'}), 404
    return flask.jsonify(analysis.analyze_pdf(path))


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
    return flask.send_file(cache_png, mimetype='image/png')


@app.route('/arrange/<path:name>/<int:page>/<int:band>')
def arrange(name, page, band):
    """中型 C12 模具排列順序:每番次 4 格(4 個模具欄位)合成圖。"""
    path = get_pdf(name)
    if not path:
        return flask.abort(404)
    res = analysis.page_analysis(path, page - 1)
    if res.get('type') != '中型' or not res.get('arrange') or band not in res['arrange']:
        return flask.abort(404)
    img = st.render_pages(path, 200)[page - 1]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    boxes = res['arrange'][band]
    scale, pad = 2, 8
    cw = max(b[2] for b in boxes) * scale + pad * 2
    ch = max(b[3] for b in boxes) * scale + pad * 2
    out = np.full((ch, 4 * cw, 3), 255, np.uint8)
    for idx, (bx, by, bw, bh) in enumerate(boxes[:4]):
        by = min(by, gray.shape[0] - bh)
        bx = min(bx, gray.shape[1] - bw)
        crop = gray[by:by + bh, bx:bx + bw]
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
        x0, y0 = idx * cw + pad, pad
        out[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
        cv2.rectangle(out, (x0, y0), (x0 + crop.shape[1] - 1, y0 + crop.shape[0] - 1), (0, 0, 0), 1)
    ok, buf = cv2.imencode('.png', out)
    resp = flask.Response(buf.tobytes(), mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/crop/<path:name>/<int:page>/<int:band>/<area>')
def crop(name, page, band, area):
    """中型表單子欄 crop 預覽: area = c14_0..2, c15_0..2, centrifuge"""
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
    return resp


@app.route('/export', methods=['POST'])
def export():
    data = flask.request.get_json(force=True)
    pdf = data.get('pdf')
    rows = data.get('rows', [])
    date_iso = data.get('date_iso', '')
    roc = data.get('date_roc', '')
    if not pdf or not roc:
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
    return flask.jsonify({'ok': True, 'path': out_path, 'rows': len(rows)})


if __name__ == '__main__':
    reload = os.environ.get('BTOOL_RELOAD') == '1'
    app.run(debug=reload, threaded=True, port=5000)
