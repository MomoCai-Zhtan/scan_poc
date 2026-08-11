# -*- coding: utf-8 -*-
"""掃描輸入工具 B MVP:PDF → 單頁聚焦 → 集合匯出 → 39欄 CSV"""
import csv
import glob
import logging
import os
import sys
import json
import uuid
from datetime import datetime

import cv2
import flask
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, 'ocr_cli')
CSV_DIR = os.path.join(ROOT, 'csv')
CACHE = os.path.join(ROOT, 'scan_entry', 'cache')
CACHE_VERSION = 2
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'scan_entry.log')
DB_PATH = os.path.join(ROOT, 'scan_entry', 'data', 'collections.db')

sys.path.insert(0, OCR)
import analysis
import structure as st
import accuracy_map as am

app = flask.Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('FLASK_SECRET', 'scan-entry-secret-2026')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

logger = logging.getLogger('scan_entry')
logger.setLevel(logging.INFO)
if not logger.handlers:
    _fmt = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    _h = logging.StreamHandler()
    _h.setFormatter(_fmt)
    logger.addHandler(_h)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        _f = logging.FileHandler(LOG_FILE, encoding='utf-8')
        _f.setFormatter(_fmt)
        logger.addHandler(_f)
    except Exception:
        logger.warning('log file handler init failed: %s', LOG_FILE)


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

# SQLite-backed collection persistence
import sqlite3

def _db_init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sid TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'band',
            pdf TEXT,
            page INTEGER,
            band INTEGER,
            date_iso TEXT,
            date_roc TEXT,
            date_disp TEXT,
            type TEXT,
            shift TEXT,
            fields TEXT,
            rows TEXT,
            added_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sid, kind, pdf, page, band)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sid ON collections(sid)")
    conn.commit()
    return conn

_db_conn = _db_init()

# In-memory cache for fast reads (session_id -> [items])
COLLECTIONS = {}

def _db_get_collection(sid):
    """Load collection from SQLite into memory cache."""
    cur = _db_conn.execute("SELECT kind, pdf, page, band, date_iso, date_roc, date_disp, type, shift, fields, rows, added_at FROM collections WHERE sid = ?", (sid,))
    items = []
    for row in cur.fetchall():
        kind, pdf, page, band, date_iso, date_roc, date_disp, type_, shift, fields, rows, added_at = row
        item = {'kind': kind, 'pdf': pdf, 'page': page, 'added_at': added_at}
        if kind == 'band':
            item['band'] = band
            item['date_iso'] = date_iso
            item['date_roc'] = date_roc
            item['date_disp'] = date_disp
            item['type'] = type_
            item['shift'] = shift
            item['fields'] = json.loads(fields) if fields else {}
        else:
            item['date_iso'] = date_iso
            item['date_roc'] = date_roc
            item['date_disp'] = date_disp
            item['type'] = type_
            item['rows'] = json.loads(rows) if rows else []
        items.append(item)
    return items

def _db_upsert_item(sid, item):
    """Insert or update a collection item in SQLite."""
    kind = item.get('kind', 'band')
    pdf = item.get('pdf')
    page = item.get('page')
    band = item.get('band') if kind == 'band' else None
    date_iso = item.get('date_iso', '')
    date_roc = item.get('date_roc', '')
    date_disp = item.get('date_disp', '')
    type_ = item.get('type', '')
    shift = item.get('shift', '')
    fields = json.dumps(item.get('fields', {}), ensure_ascii=False)
    rows = json.dumps(item.get('rows', []), ensure_ascii=False)
    added_at = item.get('added_at', datetime.now().isoformat())
    _db_conn.execute("""
        INSERT INTO collections (sid, kind, pdf, page, band, date_iso, date_roc, date_disp, type, shift, fields, rows, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sid, kind, pdf, page, band) DO UPDATE SET
            fields=excluded.fields, rows=excluded.rows, updated_at=CURRENT_TIMESTAMP
    """, (sid, kind, pdf, page, band, date_iso, date_roc, date_disp, type_, shift, fields, rows, added_at))
    _db_conn.commit()

def _db_delete_collection(sid):
    """Delete all items for a session."""
    _db_conn.execute("DELETE FROM collections WHERE sid = ?", (sid,))
    _db_conn.commit()

def _db_count(sid):
    """Count items for a session."""
    cur = _db_conn.execute("SELECT COUNT(*) FROM collections WHERE sid = ?", (sid,))
    return cur.fetchone()[0]


def list_pdfs():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, '*.pdf')))


def get_pdf(name):
    name = os.path.basename(name)
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return None
    return path


def _page_cache_path(name, page):
    return os.path.join(CACHE, '%s_p%d_analysis.json' % (name.replace('.', '_'), page))


def _page_cache_load(cache_path, name, page):
    """回傳已快取的頁面 OCR 快照;PDF 變動(mtime 不同)、版本不符或損毀則回 None。"""
    try:
        with open(cache_path, encoding='utf-8') as f:
            data = json.load(f)
        pdf_path = os.path.join(ROOT, name)
        meta = data.get('_meta', {})
        if not os.path.exists(pdf_path):
            return None
        if meta.get('pdf_mtime') != os.path.getmtime(pdf_path):
            return None
        if meta.get('version') != CACHE_VERSION:
            return None
        return data.get('result')
    except Exception:
        pass
    return None


def _page_cache_save(cache_path, name, page, result):
    try:
        os.makedirs(CACHE, exist_ok=True)
        payload = {
            '_meta': {
                'version': CACHE_VERSION,
                'pdf_mtime': os.path.getmtime(os.path.join(ROOT, name)),
            },
            'result': result,
        }
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        logger.warning('page cache save failed: %s p%d', name, page)


def _page_analysis_with_date(path, name, page):
    result = analysis.page_analysis(path, page - 1)
    roc, iso, disp = analysis.filename_date(name)
    result['date_iso'] = iso
    result['date_roc'] = roc
    result['date_disp'] = disp
    return result


@app.route('/')
def index():
    import time
    return flask.render_template('index.html', pdfs=list_pdfs(), header=HEADER, item_count=ITEM_COUNT, _ts=int(time.time()))


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
    return flask.jsonify(analysis.analyze_pdf(path, ocr=False))


@app.route('/api/pdf/<path:name>/<int:page>')
def api_pdf_page(name, page):
    """Single page analysis. With OCR by default; add ?structure_only=1 to skip OCR.
    結果以 PDF 為 key 快照至磁碟,換頁/重整不再重複 OCR。"""
    path = get_pdf(name)
    if not path:
        logger.warning('api_pdf_page not found: %s page=%d', name, page)
        return flask.jsonify({'error': 'not found'}), 404
    pages = st.render_pages(path, 200)
    if page < 1 or page > len(pages):
        logger.warning('api_pdf_page invalid page: %s page=%d (total=%d)', name, page, len(pages))
        return flask.jsonify({'error': 'invalid page'}), 404
    structure_only = flask.request.args.get('structure_only') == '1'
    cache_path = _page_cache_path(name, page)
    result = _page_cache_load(cache_path, name, page)
    if result is None or structure_only:
        logger.info('api_pdf_page %s: %s page=%d', 'structure' if structure_only else 'OCR', name, page)
        result = _page_analysis_with_date(path, name, page)
        if not structure_only:
            _page_cache_save(cache_path, name, page, result)
    else:
        logger.info('api_pdf_page cache hit: %s page=%d', name, page)
    return flask.jsonify(result)


@app.route('/api/pdf/<path:name>/<int:page>/ocr', methods=['POST'])
def api_pdf_page_ocr(name, page):
    """Re-trigger OCR for a single page (e.g., after user修正) — 強制重算並更新快照。"""
    path = get_pdf(name)
    if not path:
        logger.warning('api_pdf_page_ocr not found: %s page=%d', name, page)
        return flask.jsonify({'error': 'not found'}), 404
    pages = st.render_pages(path, 200)
    if page < 1 or page > len(pages):
        logger.warning('api_pdf_page_ocr invalid page: %s page=%d', name, page)
        return flask.jsonify({'error': 'invalid page'}), 404
    logger.info('api_pdf_page_ocr re-trigger: %s page=%d', name, page)
    result = _page_analysis_with_date(path, name, page)
    _page_cache_save(_page_cache_path(name, page), name, page, result)
    return flask.jsonify(result)


@app.route('/api/pdf/<path:name>/<int:page>/band/<int:band>/ocr', methods=['POST'])
def api_band_ocr(name, page, band):
    """Re-OCR a single band (for sparse-ink retry or user-initiated correction).
    Updates the cached page snapshot and returns the new band dict."""
    path = get_pdf(name)
    if not path:
        logger.warning('api_band_ocr not found: %s page=%d band=%d', name, page, band)
        return flask.jsonify({'error': 'not found'}), 404
    pages = st.render_pages(path, 200)
    if page < 1 or page > len(pages):
        logger.warning('api_band_ocr invalid page: %s page=%d band=%d', name, page, band)
        return flask.jsonify({'error': 'invalid page'}), 404
    logger.info('api_band_ocr: %s page=%d band=%d', name, page, band)
    band_data = analysis.re_ocr_band(path, page - 1, band)
    cache_path = _page_cache_path(name, page)
    cached = _page_cache_load(cache_path, name, page)
    if cached and band_data:
        cached.setdefault('auto_fields', {})[band] = band_data
        _page_cache_save(cache_path, name, page, cached)
    return flask.jsonify({'ok': True, 'band': band, 'fields': band_data})


@app.route('/api/accuracy/<path:name>')
def api_accuracy(name):
    """Return expected OCR accuracy for a PDF (from pre-computed baseline)."""
    key = name.replace('.pdf', '')
    cached = am.load()
    if cached and key in cached:
        return flask.jsonify(cached[key])
    # Fallback: return general estimate by form type
    return flask.jsonify({
        'pdf': name,
        'accuracy': None,
        'message': '無預先計算 baseline，開啟頁面後會自動顯示實際 OCR 準確率參考'
    })


@app.route('/api/collection', methods=['GET'])
def get_collection():
    """Get current session's collection."""
    sid = flask.session.get('sid') or str(uuid.uuid4())
    flask.session['sid'] = sid
    if sid not in COLLECTIONS:
        COLLECTIONS[sid] = _db_get_collection(sid)
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
    _db_upsert_item(sid, page_data)
    if sid not in COLLECTIONS:
        COLLECTIONS[sid] = _db_get_collection(sid)
    else:
        COLLECTIONS[sid] = _db_get_collection(sid)
    logger.info('collection POST sid=%s page=%d rows=%d total=%d', sid[:8], page_data.get('page', 0), len(page_data.get('rows', [])), len(COLLECTIONS[sid]))
    return flask.jsonify({'ok': True, 'count': len(COLLECTIONS[sid])})


@app.route('/api/collection/band', methods=['POST'])
def add_band_to_collection():
    """逐番收集:把單個番次資料加入集合(每 band = 1 列 CSV)。"""
    sid = flask.session.get('sid') or str(uuid.uuid4())
    flask.session['sid'] = sid
    data = flask.request.get_json(force=True)
    item = {
        'kind': 'band',
        'pdf': data.get('pdf'),
        'page': data.get('page'),
        'band': data.get('band'),
        'date_iso': data.get('date_iso'),
        'date_roc': data.get('date_roc'),
        'date_disp': data.get('date_disp'),
        'type': data.get('type'),
        'shift': data.get('shift'),
        'fields': data.get('fields', {}),
        'added_at': datetime.now().isoformat(),
    }
    _db_upsert_item(sid, item)
    if sid not in COLLECTIONS:
        COLLECTIONS[sid] = _db_get_collection(sid)
    else:
        COLLECTIONS[sid] = _db_get_collection(sid)
    coll = COLLECTIONS[sid]
    existing = next((i for i, it in enumerate(coll) if it.get('kind') == 'band'
                      and it.get('pdf') == item['pdf'] and it.get('page') == item['page']
                      and it.get('band') == item['band']), None)
    updated = existing is not None
    logger.info('collection band POST sid=%s pdf=%s page=%d band=%s %s total=%d',
                sid[:8], item['pdf'], item['page'], item['band'],
                'updated' if updated else 'added', len(coll))
    return flask.jsonify({'ok': True, 'count': len(coll), 'updated': updated})


@app.route('/api/collection', methods=['DELETE'])
def clear_collection():
    """Clear collection."""
    sid = flask.session.get('sid')
    if sid:
        _db_delete_collection(sid)
        if sid in COLLECTIONS:
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


# ========== Admin CRUD ==========

TEMPLATES_DIR = os.path.join(ROOT, 'ocr_cli', 'templates')
REGIONS_DIR = os.path.join(ROOT, 'ocr_cli', 'template_regions')
MAPPINGS_DIR = os.path.join(ROOT, 'ocr_cli', 'field_mappings')

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(REGIONS_DIR, exist_ok=True)
os.makedirs(MAPPINGS_DIR, exist_ok=True)


def _list_files(directory, ext='.json'):
    if not os.path.exists(directory):
        return []
    return [f for f in os.listdir(directory) if f.endswith(ext)]


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.route('/admin')
def admin_dashboard():
    return flask.render_template('admin.html')


@app.route('/admin/templates', methods=['GET'])
def admin_list_templates():
    files = [f for f in os.listdir(TEMPLATES_DIR) if f.endswith(('.png', '.jpg', '.jpeg'))] if os.path.exists(TEMPLATES_DIR) else []
    templates = []
    for f in files:
        path = os.path.join(TEMPLATES_DIR, f)
        templates.append({
            'name': f,
            'size': os.path.getsize(path),
            'modified': datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
        })
    return flask.jsonify({'templates': templates})


@app.route('/admin/templates', methods=['POST'])
def admin_create_template():
    if 'file' not in flask.request.files:
        return flask.jsonify({'error': 'no file'}), 400
    f = flask.request.files['file']
    if not f.filename or not f.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
        return flask.jsonify({'error': 'invalid file type'}), 400
    
    filename = f.filename
    if filename.lower().endswith('.pdf'):
        path = os.path.join(TEMPLATES_DIR, filename)
        f.save(path)
        pages = st.render_pages(path, 200)
        if pages:
            png_name = filename.replace('.pdf', '.png')
            cv2.imwrite(os.path.join(TEMPLATES_DIR, png_name), pages[0])
            os.remove(path)
            filename = png_name
    else:
        f.save(os.path.join(TEMPLATES_DIR, filename))
    
    return flask.jsonify({'name': filename, 'status': 'created'})


@app.route('/admin/templates/<name>', methods=['DELETE'])
def admin_delete_template(name):
    path = os.path.join(TEMPLATES_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return flask.jsonify({'status': 'deleted'})


@app.route('/admin/regions', methods=['GET'])
def admin_list_regions():
    files = _list_files(REGIONS_DIR, '.json')
    regions = []
    for f in files:
        path = os.path.join(REGIONS_DIR, f)
        data = _load_json(path)
        regions.append({
            'name': f,
            'fields': list(data.keys()) if data else [],
            'modified': datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
        })
    return flask.jsonify({'regions': regions})


@app.route('/admin/regions', methods=['POST'])
def admin_create_regions():
    data = flask.request.get_json(force=True)
    name = data.get('name', '')
    if not name.endswith('.json'):
        name += '.json'
    path = os.path.join(REGIONS_DIR, name)
    _save_json(path, data.get('fields', {}))
    return flask.jsonify({'name': name, 'status': 'created'})


@app.route('/admin/regions/<name>', methods=['GET'])
def admin_get_regions(name):
    path = os.path.join(REGIONS_DIR, name)
    data = _load_json(path)
    if data is None:
        return flask.jsonify({'error': 'not found'}), 404
    return flask.jsonify({'name': name, 'fields': data})


@app.route('/admin/regions/<name>', methods=['PUT'])
def admin_update_regions(name):
    path = os.path.join(REGIONS_DIR, name)
    data = flask.request.get_json(force=True)
    _save_json(path, data.get('fields', {}))
    return flask.jsonify({'name': name, 'status': 'updated'})


@app.route('/admin/regions/<name>', methods=['DELETE'])
def admin_delete_regions(name):
    path = os.path.join(REGIONS_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return flask.jsonify({'status': 'deleted'})


@app.route('/admin/mappings', methods=['GET'])
def admin_list_mappings():
    files = _list_files(MAPPINGS_DIR, '.json')
    mappings = []
    for f in files:
        path = os.path.join(MAPPINGS_DIR, f)
        data = _load_json(path)
        mappings.append({
            'name': f,
            'mappings': len(data) if data else 0,
            'modified': datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
        })
    return flask.jsonify({'mappings': mappings})


@app.route('/admin/mappings', methods=['POST'])
def admin_create_mapping():
    data = flask.request.get_json(force=True)
    name = data.get('name', '')
    if not name.endswith('.json'):
        name += '.json'
    path = os.path.join(MAPPINGS_DIR, name)
    _save_json(path, data.get('mappings', {}))
    return flask.jsonify({'name': name, 'status': 'created'})


@app.route('/admin/mappings/<name>', methods=['GET'])
def admin_get_mapping(name):
    path = os.path.join(MAPPINGS_DIR, name)
    data = _load_json(path)
    if data is None:
        return flask.jsonify({'error': 'not found'}), 404
    return flask.jsonify({'name': name, 'mappings': data})


@app.route('/admin/mappings/<name>', methods=['PUT'])
def admin_update_mapping(name):
    path = os.path.join(MAPPINGS_DIR, name)
    data = flask.request.get_json(force=True)
    _save_json(path, data.get('mappings', {}))
    return flask.jsonify({'name': name, 'status': 'updated'})


@app.route('/admin/mappings/<name>', methods=['DELETE'])
def admin_delete_mapping(name):
    path = os.path.join(MAPPINGS_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return flask.jsonify({'status': 'deleted'})


# ========== Web Field Selector ==========

@app.route('/selector')
def selector_page():
    template = flask.request.args.get('template', 'small')
    output = flask.request.args.get('output', '')
    return flask.render_template('field_selector.html', template=template, output=output)


@app.route('/api/selector/image/<template>')
def selector_image(template):
    name_map = {
        'small': 'small_form_blank.png',
        'medium': 'medium_form_blank.png'
    }
    filename = name_map.get(template, template + '.png')
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        return flask.abort(404)
    return flask.send_file(path, mimetype='image/png')


@app.route('/api/selector/detect', methods=['POST'])
def selector_detect():
    data = flask.request.get_json(force=True)
    template = data.get('template', 'small')
    name_map = {
        'small': 'small_form_blank.png',
        'medium': 'medium_form_blank.png'
    }
    filename = name_map.get(template, template + '.png')
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        return flask.jsonify({'error': 'template not found'}), 404
    
    pil_img = Image.open(path)
    img_rgb = np.array(pil_img)
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 11, 5)
    h, w = bw.shape
    
    horiz = bw.copy()
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 30, 1))
    horiz = cv2.morphologyEx(horiz, cv2.MORPH_OPEN, horiz_kernel, iterations=1)
    h_lines = []
    for y in range(h):
        if np.sum(horiz[y, :]) > w * 0.3 * 255:
            h_lines.append(y)
    
    vert = bw.copy()
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 30))
    vert = cv2.morphologyEx(vert, cv2.MORPH_OPEN, vert_kernel, iterations=1)
    v_lines = []
    for x in range(w):
        if np.sum(vert[:, x]) > h * 0.3 * 255:
            v_lines.append(x)
    
    def cluster(lines, threshold):
        if not lines:
            return []
        clusters = [[lines[0]]]
        for x in lines[1:]:
            if x - clusters[-1][-1] <= threshold:
                clusters[-1].append(x)
            else:
                clusters.append([x])
        return [int(np.mean(c)) for c in clusters]
    
    h_lines = cluster(h_lines, 10)
    v_lines = cluster(v_lines, 10)
    
    cells = []
    for row_idx in range(len(h_lines) - 1):
        for col_idx in range(len(v_lines) - 1):
            x0 = v_lines[col_idx]
            y0 = h_lines[row_idx]
            x1 = v_lines[col_idx + 1]
            y1 = h_lines[row_idx + 1]
            cells.append({
                'row': row_idx,
                'col': col_idx,
                'x': x0, 'y': y0,
                'w': x1 - x0, 'h': y1 - y0
            })
    
    return flask.jsonify({
        'cells': cells,
        'h_lines': h_lines,
        'v_lines': v_lines,
        'rows': len(h_lines) - 1,
        'cols': len(v_lines) - 1
    })


@app.route('/favicon.ico')
def favicon():
    return flask.Response('', status=204)


if __name__ == '__main__':
    reload = os.environ.get('BTOOL_RELOAD') == '1'
    logger.info('starting scan_entry on :5000 reload=%s', reload)
    app.run(debug=reload, threaded=True, port=5000)
