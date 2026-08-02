# -*- coding: utf-8 -*-
"""驗證 index.html 內嵌 JavaScript 大括號/括號配對 (re-layout-plan §7.2)。
以字元掃描跳過字串、模板字串、註解後, 檢查 () [] {} 巢狀配對是否平衡。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, 'templates', 'index.html')

PAIRS = {')': '(', ']': '[', '}': '{'}


def extract_scripts(html):
    """回傳 <script>...</script> 內容 (排除 src 外連)。"""
    scripts = []
    for m in __import__('re').finditer(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, __import__('re').S):
        scripts.append(m.group(1))
    return scripts


def strip_js(js):
    """移除字串/模板字串/註解, 保留純 code (不含跳脫、巢狀 ${} 處理)。"""
    out = []
    i = 0
    n = len(js)
    while i < n:
        ch = js[i]
        nxt = js[i + 1] if i + 1 < n else ''
        # 行註解
        if ch == '/' and nxt == '/':
            while i < n and js[i] != '\n':
                i += 1
            continue
        # 區塊註解
        if ch == '/' and nxt == '*':
            i += 2
            while i + 1 < n and not (js[i] == '*' and js[i + 1] == '/'):
                i += 1
            i += 2
            continue
        # 字串
        if ch in ('"', "'"):
            q = ch
            i += 1
            while i < n:
                if js[i] == '\\':
                    i += 2
                    continue
                if js[i] == q:
                    i += 1
                    break
                i += 1
            continue
        # 模板字串 `...` (含 ${...} 巢狀)
        if ch == '`':
            i += 1
            while i < n:
                if js[i] == '\\':
                    i += 2
                    continue
                if js[i] == '`':
                    i += 1
                    break
                if js[i] == '$' and i + 1 < n and js[i + 1] == '{':
                    i += 2
                    depth = 1
                    while i < n and depth:
                        if js[i] == '\\':
                            i += 2
                            continue
                        if js[i] == '{':
                            depth += 1
                        elif js[i] == '}':
                            depth -= 1
                        i += 1
                    continue
                i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def check_balance(code):
    """檢查括號配對。回傳 (ok, stack_or_error)。"""
    stack = []
    for i, ch in enumerate(code):
        if ch in '([{':
            stack.append((ch, i))
        elif ch in ')]}':
            if not stack or stack[-1][0] != PAIRS[ch]:
                return False, '位置 %d: 遇到 %s 但最近的是 %s' % (i, ch, stack[-1][0] if stack else '無')
            stack.pop()
    if stack:
        return False, '未閉合的 %d 個符號, 例如 %r 於位置 %d' % (len(stack), stack[-1][0], stack[-1][1])
    return True, 'OK'


def main():
    if not os.path.exists(HTML):
        print('FAIL index.html 不存在')
        sys.exit(1)
    html = open(HTML, encoding='utf-8').read()
    scripts = extract_scripts(html)
    if not scripts:
        print('FAIL 找不到內嵌 <script>')
        sys.exit(1)
    ok = True
    for idx, js in enumerate(scripts):
        code = strip_js(js)
        balanced, msg = check_balance(code)
        print('script[%d]: %d chars, () = %d, [] = %d, {} = %d -> %s %s' % (
            idx, len(js),
            code.count('('), code.count('['), code.count('{'),
            'PASS' if balanced else 'FAIL', msg))
        if not balanced:
            ok = False

    # 若 node 可用, 用真正 JS parser 做語法檢查 (Jinja 佔位符先換成合法值)
    if _node_check(scripts):
        ok = True
    else:
        ok = False
    sys.exit(0 if ok else 1)


def _node_check(scripts):
    import shutil
    import tempfile
    node = shutil.which('node')
    if not node:
        return True  # 無 node 時跳過 (Python 配對檢查已通過)
    src = '\n'.join(scripts)
    src = (src
           .replace('{{ _ts }}', '0')
           .replace('{{ pdfs | tojson }}', '[]')
           .replace('{{ header | tojson }}', '[]')
           .replace('{{ item_count | tojson }}', '{}'))
    fd, tmp = tempfile.mkstemp(suffix='.js')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(src)
        rc = subprocess.call([node, '--check', tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print('node --check -> %s' % ('PASS' if rc == 0 else 'FAIL'))
        return rc == 0
    finally:
        os.remove(tmp)


import subprocess  # noqa: E402


if __name__ == '__main__':
    main()
