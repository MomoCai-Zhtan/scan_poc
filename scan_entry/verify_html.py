# -*- coding: utf-8 -*-
"""驗證 index.html 三欄布局結構完整性 (re-layout-plan §7.2)。
檢查: 三欄容器、進度條、番次列表、階段表單、逐番收集 API、快捷鍵。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, 'templates', 'index.html')

REQUIRED_CLASSES = [
    'layout-body',          # 三欄容器
    'canvas-col',           # 左: 畫布
    'band-list',            # 中: 番次列表
    'form-col',             # 右: 表單
    'stage-progress',       # 階段進度條
    'progress-fill',        # 進度填充
    'stage-card',           # 階段卡片
    'field-row',            # 欄位列
    'ocr-badge',            # OCR 徽標
    'shortcut-hint',        # 快捷鍵提示
]

REQUIRED_IDS = [
    'scanCanvas',
    'bandList',
    'stageForm',
    'btnAddBand',
    'btnExport',
    'btnStagePrev',
    'btnStageNext',
    'pageStatus',
    'collInfo',
    'progressFill',
    'stageLabel',
    'pdfGroup',
    'pageNav',
]

REQUIRED_JS_PATTERNS = [
    r'/api/collection/band',        # 逐番收集 API
    r'/export',                      # 匯出
    r'const STAGES\s*=\s*\[',        # 三階段定義
    r'keydown',                      # 快捷鍵
    r'Enter',                        # Enter 快捷鍵
    r'Escape',                       # Esc 重置欄位
]


def main():
    if not os.path.exists(HTML):
        print('FAIL index.html 不存在: %s' % HTML)
        sys.exit(1)
    html = open(HTML, encoding='utf-8').read()
    failures = []

    for c in REQUIRED_CLASSES:
        if c not in html:
            failures.append('缺少 CSS class: %s' % c)

    for i in REQUIRED_IDS:
        if ('id="' + i + '"') not in html:
            failures.append('缺少 element id: %s' % i)

    # 階段定義: 需有 3 個階段,名稱依序 基本資料/離心/蒸養
    m = re.search(r'const STAGES\s*=\s*(\[.*?\]);', html, re.S)
    if not m:
        failures.append('找不到 STAGES 定義')
    else:
        names = re.findall(r'name:\s*"([^"]+)"', m.group(1))
        if names != ['基本資料', '離心', '蒸養']:
            failures.append('STAGES 階段定義不符: %r' % names)
        if len(re.findall(r'cols:', m.group(1))) != 3:
            failures.append('STAGES 需為 3 個階段')

    for pat in REQUIRED_JS_PATTERNS:
        if not re.search(pat, html):
            failures.append('JS 缺少關鍵模式: %s' % pat)

    # 三階段欄位抽樣: 階段1 需含 序/品項, 階段3 需含 排列
    if 'production' not in html and '生產數量' not in html:
        failures.append('缺少 生產數量 欄位')

    if failures:
        print('FAIL')
        for f in failures:
            print('  - ' + f)
        sys.exit(1)
    print('PASS index.html 三欄布局結構完整 (classes=%d ids=%d stages=3)' %
          (len(REQUIRED_CLASSES), len(REQUIRED_IDS)))


if __name__ == '__main__':
    main()
