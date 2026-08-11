# -*- coding: utf-8 -*-
"""後台(Admin)路由:Template / Region / Field Mapping 管理 + 欄位選擇器。

跟 app.py 的前台(掃描輸入主頁)分開放,方便獨立維護權限——本檔案內所有
路由都會經過 `_require_login` 檢查,只有 `/admin/login` 例外。
"""
import json
import logging
import os
import sys

import cv2
import flask
import numpy as np
from datetime import datetime
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, 'ocr_cli')
sys.path.insert(0, OCR)
import structure as st
import detect_lib

logger = logging.getLogger('scan_entry')

admin_bp = flask.Blueprint('admin', __name__)

TEMPLATES_DIR = os.path.join(ROOT, 'ocr_cli', 'templates')
REGIONS_DIR = os.path.join(ROOT, 'ocr_cli', 'template_regions')
MAPPINGS_DIR = os.path.join(ROOT, 'ocr_cli', 'field_mappings')

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(REGIONS_DIR, exist_ok=True)
os.makedirs(MAPPINGS_DIR, exist_ok=True)

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
if os.environ.get('ADMIN_PASSWORD_HASH'):
    ADMIN_PASSWORD_HASH = os.environ['ADMIN_PASSWORD_HASH']
else:
    _default_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    ADMIN_PASSWORD_HASH = generate_password_hash(_default_password)
    if not os.environ.get('ADMIN_PASSWORD'):
        logger.warning('ADMIN_PASSWORD 未設定,使用預設密碼 "admin123" — 正式環境請設定環境變數 ADMIN_PASSWORD 或 ADMIN_PASSWORD_HASH')

# 這個 blueprint 裡只有登入頁本身是公開的,其餘一律要求已登入。
# 頁面型路由(回傳 HTML)未登入時導去 /admin/login;API 型路由(回傳 JSON)未登入時回 401。
_PAGE_ENDPOINTS = {'admin.admin_dashboard', 'admin.selector_page'}


@admin_bp.before_request
def _require_login():
    if flask.request.endpoint == 'admin.admin_login':
        return None
    if flask.session.get('is_admin'):
        return None
    if flask.request.endpoint in _PAGE_ENDPOINTS:
        return flask.redirect(flask.url_for('admin.admin_login', next=flask.request.path))
    return flask.jsonify({'error': 'unauthorized'}), 401


@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if flask.request.method == 'POST':
        username = flask.request.form.get('username', '')
        password = flask.request.form.get('password', '')
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            flask.session['is_admin'] = True
            next_url = flask.request.form.get('next') or flask.url_for('admin.admin_dashboard')
            if not next_url.startswith('/'):
                next_url = flask.url_for('admin.admin_dashboard')
            logger.info('admin login: %s', username)
            return flask.redirect(next_url)
        logger.warning('admin login failed: %s', username)
        return flask.render_template('admin_login.html', error='帳號或密碼錯誤',
                                      next=flask.request.form.get('next', '')), 401
    return flask.render_template('admin_login.html', error=None, next=flask.request.args.get('next', ''))


@admin_bp.route('/admin/logout', methods=['POST'])
def admin_logout():
    flask.session.pop('is_admin', None)
    return flask.redirect(flask.url_for('admin.admin_login'))


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


@admin_bp.route('/admin')
def admin_dashboard():
    return flask.render_template('admin.html')


@admin_bp.route('/admin/templates', methods=['GET'])
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


@admin_bp.route('/admin/templates', methods=['POST'])
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


@admin_bp.route('/admin/templates/<name>', methods=['DELETE'])
def admin_delete_template(name):
    path = os.path.join(TEMPLATES_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return flask.jsonify({'status': 'deleted'})


@admin_bp.route('/admin/regions', methods=['GET'])
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


@admin_bp.route('/admin/regions', methods=['POST'])
def admin_create_regions():
    data = flask.request.get_json(force=True)
    name = data.get('name', '')
    if not name.endswith('.json'):
        name += '.json'
    path = os.path.join(REGIONS_DIR, name)
    _save_json(path, data.get('fields', {}))
    return flask.jsonify({'name': name, 'status': 'created'})


@admin_bp.route('/admin/regions/<name>', methods=['GET'])
def admin_get_regions(name):
    path = os.path.join(REGIONS_DIR, name)
    data = _load_json(path)
    if data is None:
        return flask.jsonify({'error': 'not found'}), 404
    return flask.jsonify({'name': name, 'fields': data})


@admin_bp.route('/admin/regions/<name>', methods=['PUT'])
def admin_update_regions(name):
    path = os.path.join(REGIONS_DIR, name)
    data = flask.request.get_json(force=True)
    _save_json(path, data.get('fields', {}))
    return flask.jsonify({'name': name, 'status': 'updated'})


@admin_bp.route('/admin/regions/<name>', methods=['DELETE'])
def admin_delete_regions(name):
    path = os.path.join(REGIONS_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return flask.jsonify({'status': 'deleted'})


@admin_bp.route('/admin/mappings', methods=['GET'])
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


@admin_bp.route('/admin/mappings', methods=['POST'])
def admin_create_mapping():
    data = flask.request.get_json(force=True)
    name = data.get('name', '')
    if not name.endswith('.json'):
        name += '.json'
    path = os.path.join(MAPPINGS_DIR, name)
    _save_json(path, data.get('mappings', {}))
    return flask.jsonify({'name': name, 'status': 'created'})


@admin_bp.route('/admin/mappings/<name>', methods=['GET'])
def admin_get_mapping(name):
    path = os.path.join(MAPPINGS_DIR, name)
    data = _load_json(path)
    if data is None:
        return flask.jsonify({'error': 'not found'}), 404
    return flask.jsonify({'name': name, 'mappings': data})


@admin_bp.route('/admin/mappings/<name>', methods=['PUT'])
def admin_update_mapping(name):
    path = os.path.join(MAPPINGS_DIR, name)
    data = flask.request.get_json(force=True)
    _save_json(path, data.get('mappings', {}))
    return flask.jsonify({'name': name, 'status': 'updated'})


@admin_bp.route('/admin/mappings/<name>', methods=['DELETE'])
def admin_delete_mapping(name):
    path = os.path.join(MAPPINGS_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return flask.jsonify({'status': 'deleted'})


# ========== Web Field Selector ==========

@admin_bp.route('/selector')
def selector_page():
    template = flask.request.args.get('template', 'small')
    output = flask.request.args.get('output', '')
    return flask.render_template('field_selector.html', template=template, output=output)


@admin_bp.route('/api/selector/image/<template>')
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


@admin_bp.route('/api/selector/detect', methods=['POST'])
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

    cells, h_lines, v_lines = detect_lib.detect_table_cells(img_bgr)

    return flask.jsonify({
        'cells': cells,
        'h_lines': h_lines,
        'v_lines': v_lines,
        'rows': max(len(h_lines) - 1, 0),
        'cols': max(len(v_lines) - 1, 0)
    })


@admin_bp.route('/api/selector/save', methods=['POST'])
def selector_save():
    data = flask.request.get_json(force=True)
    template = data.get('template', 'small')
    fields = data.get('fields', {})

    if not fields:
        return flask.jsonify({'error': 'no fields to save'}), 400

    name_map = {
        'small': 'small_form',
        'medium': 'medium_form'
    }
    base_name = name_map.get(template, template + '_form')
    filename = base_name + '_v1.json'
    path = os.path.join(REGIONS_DIR, filename)

    _save_json(path, fields)
    logger.info('selector save: %s fields=%d path=%s', template, len(fields), path)

    return flask.jsonify({'ok': True, 'name': filename, 'fields': len(fields)})
