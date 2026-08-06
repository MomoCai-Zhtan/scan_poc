# -*- coding: utf-8 -*-
"""驗證 app 模組可正常載入 (繼承邏輯已套用)。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scan_entry'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app
print('app OK, routes:', len(list(app.app.url_map.iter_rules())))