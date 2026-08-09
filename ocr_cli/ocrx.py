# -*- coding: utf-8 -*-
"""Mistral OCR integration: send page image to Mistral OCR API, return markdown."""
import os, sys, base64, logging, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import httpx
import numpy as np

ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'scan_entry', 'logs', 'scan_entry.log')

log = logging.getLogger('ocrx')
if not log.handlers:
    log.setLevel(logging.INFO)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        _f = logging.FileHandler(LOG_FILE, encoding='utf-8')
        _f.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s [ocrx] %(message)s',
                                          datefmt='%Y-%m-%d %H:%M:%S'))
        log.addHandler(_f)
    except Exception:
        pass

def _load_env():
    cfg = {}
    if not os.path.exists(ENV):
        return cfg
    with open(ENV, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    return cfg

_cfg = _load_env()
OCR_API_KEY = _cfg.get('MISTRAL_API_KEY', '')
OCR_MODEL = _cfg.get('MISTRAL_MODEL', 'mistral-ocr-latest')
OCR_API_URL = _cfg.get('MISTRAL_API_URL', 'https://api.mistral.ai/v1/ocr')


def ocr_image(bgr):
    """Send an in-memory BGR image to Mistral OCR. Returns markdown string."""
    if not OCR_API_KEY:
        log.error('OCR aborted: MISTRAL_API_KEY not set')
        return None
    t0 = time.time()
    _, buf = cv2.imencode('.png', bgr)
    b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

    headers = {'Authorization': f'Bearer {OCR_API_KEY}', 'Content-Type': 'application/json'}
    data = {
        'model': OCR_MODEL,
        'document': {'type': 'image_url', 'image_url': f'data:image/png;base64,{b64}'},
        'include_image_base64': False,
    }
    try:
        resp = httpx.post(OCR_API_URL, headers=headers, json=data, timeout=120)
    except Exception as e:
        log.error('OCR request exception: %s', repr(e))
        return None
    dt = time.time() - t0
    if resp.status_code != 200:
        log.error('OCR api status=%d elapsed=%.1fs body=%.150s', resp.status_code, dt, resp.text)
        return None
    result = resp.json()
    pages_data = result.get('pages', [])
    if pages_data:
        md = pages_data[0].get('markdown', '')
        log.info('OCR ok len=%d elapsed=%.1fs', len(md), dt)
        return md
    log.warning('OCR api 200 but no pages (elapsed=%.1fs)', dt)
    return None


def ocr_page(pdf_path, page_index):
    """Send a single PDF page to Mistral OCR. Returns markdown string."""
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    md = ocr_image(bgr)
    log.info('ocr_page %s p%d -> %s', os.path.basename(pdf_path), page_index + 1,
             'ok' if md else 'FAIL')
    return md


def ocr_crop(pdf_path, page_index, x, y, w, h, scale=2, pad=12):
    """OCR a crop region (with upscale + white padding for context). Returns markdown."""
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    y = min(max(y, 0), img.shape[0] - h)
    x = min(max(x, 0), img.shape[1] - w)
    crop = img[y:y + h, x:x + w]
    if scale != 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    canvas = np.full((crop.shape[0] + pad * 2, crop.shape[1] + pad * 2, 3), 255, np.uint8)
    canvas[pad:pad + crop.shape[0], pad:pad + crop.shape[1]] = crop
    md = ocr_image(cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
    log.info('ocr_crop %s p%d box=(%d,%d,%d,%d) -> %s', os.path.basename(pdf_path), page_index + 1,
             x, y, w, h, 'ok' if md else 'FAIL')
    return md


def ocr_band_with_header(pdf_path, page_index, y0, y1, x0=80, x1=1600,
                         hdr_top=240, hdr_bottom=380):
    """Composite crop: column header strip stacked above a single band row.

    Gives Mistral OCR the column-label context that makes per-band parsing
    reliable (header labels sit at page top, so a naive y0-offset crop would
    clip the previous band for any band past the first).
    """
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    hdr = img[max(0, hdr_top):hdr_bottom, x0:x1]
    band = img[y0:min(y1, img.shape[0]), x0:x1]
    gap = 10
    H = hdr.shape[0] + band.shape[0] + gap
    canvas = np.full((H, hdr.shape[1], 3), 255, np.uint8)
    canvas[0:hdr.shape[0]] = hdr
    canvas[hdr.shape[0] + gap: hdr.shape[0] + gap + band.shape[0]] = band
    md = ocr_image(cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
    log.info('ocr_band %s p%d band_y=(%d,%d) -> %s', os.path.basename(pdf_path), page_index + 1,
             y0, y1, 'ok' if md else 'FAIL')
    return md


def ocr_band_with_header(pdf_path, page_index, y0, y1, x0=80, x1=1600,
                         hdr_top=240, hdr_bottom=380):
    """Composite crop: column header strip stacked above a single band row.

    Gives Mistral OCR the column-label context that makes per-band parsing
    reliable (header labels sit at page top, so a naive y0-offset crop would
    clip the previous band for any band past the first).
    """
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    hdr = img[max(0, hdr_top):hdr_bottom, x0:x1]
    band = img[y0:min(y1, img.shape[0]), x0:x1]
    gap = 10
    H = hdr.shape[0] + band.shape[0] + gap
    canvas = np.full((H, hdr.shape[1], 3), 255, np.uint8)
    canvas[0:hdr.shape[0]] = hdr
    canvas[hdr.shape[0] + gap: hdr.shape[0] + gap + band.shape[0]] = band
    md = ocr_image(cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
    log.info('ocr_band %s p%d band_y=(%d,%d) -> %s', os.path.basename(pdf_path), page_index + 1,
             y0, y1, 'ok' if md else 'FAIL')
    return md


def parse_mid_table(markdown):
    """Parse Mistral OCR markdown table into structured field values for medium form.

    Returns dict: {'fan': str, 'item': str, 'molds': [...], 'centrifuge': (start, end),
                   'speeds': [...], 'speed_times': [...], 'steam_pool': str}
    per band index.
    """
    lines = markdown.split('\n')
    table_lines = [l for l in lines if l.startswith('|')]
    if not table_lines:
        return {}

    parsed = [[c.strip() for c in line.strip('|').split('|')] for line in table_lines]
    if len(parsed) < 2:
        return {}

    def has_digits(cell):
        return bool(re.search(r'\d', cell))

    data_rows = []
    for row in parsed:
        if '---' in row:
            continue
        digit_count = sum(1 for c in row if has_digits(c))
        if digit_count >= 3:
            data_rows.append(row)

    if len(data_rows) < 2:
        return {}

    bands = {}
    band_idx = 0
    i = 0
    while i + 1 < len(data_rows):
        r1 = data_rows[i]
        r2 = data_rows[i + 1]

        # --- R1 parsing ---

        # 番次: first cell with "番" + digit
        fan = ''
        for cell in r1[:3]:
            m = re.search(r'(\d+)', cell)
            if m:
                fan = m.group(1)
                break

        # Find "管模" position first — anchors both item (cell right before it) and mold
        # extraction. A fixed index for 品項 breaks whenever the OCR table gains/loses a
        # leading cell (e.g. 番次 split across two cells), silently pulling in C3's content.
        mold_label = -1
        for j, c in enumerate(r1):
            if '管模' in c:
                mold_label = j
                break

        # 品項: cell right before "管模" label (anchored); falls back to cell 1 if label missing
        item_idx = mold_label - 1 if mold_label >= 1 else 1
        item = r1[item_idx] if item_idx < len(r1) else ''
        if '管模' in item:
            item = item.replace('管模', '').strip()
        item = normalize_item(item)

        # Mold numbers: numeric cells after 管模 label (up to 4, 中型 轉位1-4)
        molds = []
        if mold_label >= 0:
            for k in range(1, 5):
                idx = mold_label + k
                if idx < len(r1):
                    nums = re.findall(r'\d+', r1[idx])
                    if nums:
                        molds.append(nums[0])
                    else:
                        molds.append('')
                else:
                    molds.append('')
        else:
            molds = ['', '', '', '']

        # Speeds: find 3-digit numbers (200-1000) in cells AFTER mold section
        # Skip fan/item/mold cells (0..mold_label+4)
        speed_start = mold_label + 5 if mold_label >= 0 else 4
        speeds = []
        for c in r1[speed_start:]:
            for n in re.findall(r'\d{3}', c):
                val = int(n)
                if 200 <= val <= 1100:
                    speeds.append(n)
        speeds = speeds[:4]

        # Steam pool: single digit (1-9) in cells after speeds
        pool = ''
        search_start = speed_start
        for c in r1[search_start:]:
            nums = re.findall(r'(\d)', c)
            if nums and int(nums[0]) <= 9 and len(c.strip()) <= 2:
                pool = nums[0]
                break

        # --- R2 parsing ---

        # Find "時間" label position
        time_label = -1
        for j, c in enumerate(r2):
            if '時間' in c:
                time_label = j
                break

        # Centrifuge time: 4-digit numbers (HHMM) in R2, skipping 1-2 digit speed times
        # Note: 下午 (afternoon) sessions can run past 1600 (e.g. 1615 ~ 1655), so the
        # upper bound must allow the full clock range — only the 600 floor guards against
        # stray low 4-digit numbers.
        cent_nums = []
        for c in r2:
            for n in re.findall(r'\d{4}', c):
                if 600 <= int(n) <= 2359:
                    cent_nums.append(n)
        cent_start = cent_nums[0] if cent_nums else ''
        cent_end = cent_nums[1] if len(cent_nums) >= 2 else ''

        # Speed times: 1-2 digit numbers (1-20) in cells that DON'T contain 4-digit times
        speed_times = []
        for c in r2:
            if re.search(r'\d{4}', c):
                continue  # skip centrifuge time cells
            nums = re.findall(r'\d{1,2}', c)
            for n in nums:
                val = int(n)
                if 1 <= val <= 20:
                    speed_times.append(n)
        speed_times = speed_times[:4]

        bands[band_idx] = {
            'fan': fan,
            'item': item,
            'molds': molds,
            'centrifuge': (cent_start, cent_end),
            'speeds': speeds,
            'speed_times': speed_times,
            'steam_pool': pool,
            'arrange': '',
            'c14': [],
            'c15': [],
        }
        band_idx += 1
        i += 2

    if bands:
        _validate_fans(bands)

    return bands


def _validate_fans(bands):
    """Validate 番次 sequence and clear obviously-wrong values.

    Rules:
    - fan must be integer 1-99
    - if fan is 3+ digits (>=100), likely misread from neighboring speed/temp cell → clear
    - consecutive fans should differ by at most 10; outlier → clear
    """
    keys = sorted(k for k in bands if isinstance(bands[k], dict))
    prev_fan = 0
    for k in keys:
        b = bands[k]
        fan = b.get('fan', '')
        if not fan:
            continue
        try:
            fv = int(fan)
        except (TypeError, ValueError):
            b['fan'] = ''
            continue
        if not (1 <= fv <= 99):
            b['fan'] = ''
            continue
        if fv >= 100:
            b['fan'] = ''
            continue
        if prev_fan and abs(fv - prev_fan) > 10:
            b['fan'] = ''
            continue
        prev_fan = fv


def _stack_cells(img, cells, scale=5, pad=24):
    """Stack multiple crop cells vertically into one padded, enlarged image."""
    import numpy as np
    crops = []
    for sx, sy, sw, sh in cells:
        sy = min(max(sy, 0), img.shape[0] - sh)
        sx = min(max(sx, 0), img.shape[1] - sw)
        crop = img[sy:sy + sh, sx:sx + sw]
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        crops.append(crop)
    if not crops:
        return None
    h_max = max(c.shape[0] for c in crops)
    w_max = max(c.shape[1] for c in crops)
    canvas = np.full((h_max * len(crops) + pad * 2 * len(crops), w_max + pad * 2, 3), 255, np.uint8)
    y = 0
    for c in crops:
        canvas[y + pad:y + pad + c.shape[0], pad:pad + c.shape[1]] = c
        y += c.shape[0] + pad * 2
    return canvas


def _ink_density(gray_img):
    """Return fraction of non-white pixels (0-1) for a grayscale crop."""
    if gray_img is None or gray_img.size == 0:
        return 0
    return float(np.sum(gray_img < 200)) / gray_img.size


def ocr_c14c15_crop(pdf_path, page_index, cells, scale=5, pad=24, min_ink=0.02):
    """Crop multiple C14/C15 sub-cells, stack vertically, enlarge, send to OCR.

    C14/C15 cells are narrow (72x58px) — 5x enlargement gives ~360x290px.
    Skips OCR if ink density is too low (sparse handwriting = not worth API call).
    Returns markdown string, or None if skipped/failed.
    """
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # Check ink density of first cell — if too sparse, skip
    if cells:
        sx, sy, sw, sh = cells[0]
        sy = min(max(sy, 0), img.shape[0] - sh)
        sx = min(max(sx, 0), img.shape[1] - sw)
        cell_gray = cv2.cvtColor(img[sy:sy + sh, sx:sx + sw], cv2.COLOR_RGB2GRAY)
        if _ink_density(cell_gray) < min_ink:
            return None

    canvas = _stack_cells(img, cells, scale=scale, pad=pad)
    if canvas is None:
        return None
    return ocr_image(canvas)


def parse_arrange_circles(markdown):
    """Parse circled digits from a C13 (模具排列順序) crop markdown.

    Returns list of up to 4 digit strings, in reading order (left→right).
    """
    import re
    out = []
    for line in markdown.split('\n'):
        for n in re.findall(r'\d+', line):
            if 0 < int(n) <= 99:
                out.append(n)
    return out[:4]


def normalize_item(raw):
    """Normalize OCR raw 品項 text to the canonical GT convention.

    The handwritten 品項 cell encodes product family + spec that OCR reads with
    noise, e.g.:
        "800×2 700×1"  → 800          (mold config, base number kept)
        "900 人孔/1孔/…" → P900        (P-type, 900 only ever appears as P900 in GT)
        "1200 …孔"       → P1200
        "1200 上型/乙型/…" → E型 1200
        "400 四周/四角"   → 400加厚
        "400 2.4"        → 400_2.4
        "800 2*35"       → E型 800_2.35
        "1350 1.15m…"    → T型 1350_1.15
    Conservative: pure numbers and already-canonical forms pass through.
    """
    import re
    if not raw:
        return raw
    s = re.sub(r'\s+', ' ', raw.strip())
    s = s.replace('×', 'x').replace('＊', '*').replace('·', '.')
    s = s.translate({ord(f): ord(d) for f, d in zip('０１２３４５６７８９．', '0123456789.')})

    canon = r'(P\d+|T型 [\d.]+_[\d.]+|E型 [\d.]+(_[\d.]+)?|400加厚|\d+_[\d.]+|(?:300|400|500|600|700|800))'
    if re.fullmatch(canon, s):
        return s

    m = re.match(r'(\d{3,4})\s*[xX]\d', s)
    if m:
        return m.group(1)

    if re.match(r'^900', s):
        return 'P900'
    if '1000' in s:
        return 'E型 1000'
    if re.match(r'^1350.*1\.15', s):
        return 'T型 1350_1.15'
    if re.match(r'^1350', s):
        return 'E型 1350'
    if re.match(r'^400.*(加|四周|四角|四隅)', s):
        return '400加厚'
    if re.match(r'^400\D*2\D*4', s):
        return '400_2.4'
    if re.match(r'^700\D*0\D*5', s):
        return '700_0.5'
    if re.match(r'^800.*2\D*35', s):
        return 'E型 800_2.35'
    if re.match(r'^1200.*2\D*35', s):
        return 'E型 1200_2.35'
    if re.match(r'^1200.*孔', s):
        return 'P1200'
    if re.match(r'^1200', s):
        return 'E型 1200'
    if re.match(r'^800.*型', s):
        return 'E型 800'
    if re.fullmatch(r'\d{3,4}', s):
        return s
    return s


_ITEM_VOCAB = None


def _item_vocab():
    """載入 scan_entry/item_count.csv 的品項欄作為已知詞彙表 (供可信度檢查)。"""
    global _ITEM_VOCAB
    if _ITEM_VOCAB is None:
        import csv
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'scan_entry', 'item_count.csv')
        vocab = set()
        try:
            with open(path, encoding='utf-8-sig') as f:
                for row in csv.reader(f):
                    if row and row[0] and row[0] != '品項':
                        vocab.add(row[0])
        except OSError:
            pass
        _ITEM_VOCAB = vocab
    return _ITEM_VOCAB


def flag_item_uncertain(bands):
    """為品項標記可信度旗標 (只加提示,不覆蓋原值,供前端顯示複核提醒):
      - 'vocab':    正規化後的品項不在 item_count.csv 已知詞彙表內
      - 'neighbor': 與同頁最近的前後「真實讀到」番次品項不同,但那兩個前後番彼此相同
                     (同一批生產通常連續多番品項不變,單一番不同很可能是誤讀,例如
                     欄位錯位讀到鄰欄數字)

    只評估「真實讀到」的品項 (本輪非繼承而來),避免跟既有「繼承」徽標語意重疊。
    """
    vocab = _item_vocab()
    keys = sorted(k for k in bands if isinstance(bands.get(k), dict))

    def real_item(k):
        b = bands[k]
        if ('item', 0) in (b.get('inherited') or []):
            return None
        return b.get('item') or None

    for idx, bi in enumerate(keys):
        b = bands[bi]
        item = real_item(bi)
        if not item:
            continue
        reasons = []
        if vocab and item not in vocab:
            reasons.append('vocab')
        prev_item = next((real_item(keys[j]) for j in range(idx - 1, -1, -1) if real_item(keys[j])), None)
        next_item = next((real_item(keys[j]) for j in range(idx + 1, len(keys)) if real_item(keys[j])), None)
        if prev_item and next_item and prev_item == next_item and item != prev_item:
            reasons.append('neighbor')
        if reasons:
            b['item_uncertain'] = reasons
    return bands


# 繼承欄位定義: (field, [indexes]) — 空白時從上一番複製
# speeds[1..3] = 慢/中/高速轉速 (加料轉速不繼承, 使用者明示)
# temps[0..2]  = 蒸養溫度1~3
# stages[0..2] = 蒸養階段1~3
# item         = 品項 (純字串, 從上一番; 使用者明示「序」忽略)
INHERIT_FIELDS = {
    'speeds': [0, 1, 2, 3],
    'speed_times': [0, 1, 2, 3],
    'temps': [0, 1, 2],
    'stages': [0, 1, 2],
    'item': None,   # None = 純字串欄位, 整欄繼承
}


def inherit_fields(bands):
    """向前繼承:空白欄位從上一番複製。

    繼承欄位:
      - speeds[1..3] 慢/中/高速轉速 (加料轉速不繼承)
      - temps[0..2]  蒸養溫度1~3
      - stages[0..2] 蒸養階段1~3
      - item         品項 (品項為空且模具編號非空才繼承; 「序」忽略)
      - pool_time    入池時間 (同蒸養池回填: 後番空白入池時間 = 同池前番的入池時間)

    只填補空白,不覆蓋已有值。
    列表欄位 (speeds/temps/stages) 繼承來源 = 最近有值番次 (含繼承值);
    品項繼承來源 = 最近「真實讀到的 C2」(非繼承值, 避免連鎖繼承錯誤擴散)。
    被繼承的欄位記錄在 band['inherited'] = [(field, idx), ...] 供前端標示。
    """
    prev = {}
    pool_times = {}   # steam_pool -> 最近入池時間
    for bi in sorted(bands.keys()):
        b = bands[bi]
        if not isinstance(b, dict):
            continue
        inherited = []

        # --- 列表欄位繼承 (speeds[1..3] / temps / stages) ---
        for field, idxs in INHERIT_FIELDS.items():
            if field == 'item':
                continue
            vals = b.get(field)
            if not isinstance(vals, (list, tuple)):
                continue
            pv = prev.get(field)
            if not pv:
                continue
            for i in idxs:
                if i < len(vals) and not vals[i] and i < len(pv) and pv[i]:
                    vals[i] = pv[i]
                    inherited.append((field, i))

        # --- 品項繼承: 品項為空 且 模具編號非空 才繼承 ---
        # 來源 = 最近「真實讀到的 C2 品項」(非繼承值), 避免連鎖繼承錯誤擴散
        if not b.get('item') and prev.get('item'):
            molds = b.get('molds') or []
            if any(molds):
                b['item'] = prev['item']
                inherited.append(('item', 0))

        # --- 入池時間同池回填: 後番空白入池時間 = 同池前番的入池時間 ---
        pool = b.get('steam_pool')
        if pool:
            if not b.get('pool_time') and pool in pool_times:
                b['pool_time'] = pool_times[pool]
                inherited.append(('pool_time', 0))
                log.info('pool_time backfill: band %d pool=%s pool_time=%s', bi, pool, pool_times[pool])
            elif b.get('pool_time'):
                log.info('pool_time skip (already set): band %d pool=%s pool_time=%s', bi, pool, b['pool_time'])
            else:
                log.info('pool_time no match: band %d pool=%s pool_times=%s', bi, pool, list(pool_times.keys()))

        if inherited:
            b['inherited'] = inherited

        # --- 更新 prev ---
        # 品項: 只記錄「真實讀到的 C2」(非繼承值), 避免連鎖繼承錯誤擴散
        # 列表欄位 (speeds/temps/stages): 記錄有值欄位 (含繼承值, 讓下一番可繼續繼承)
        for field, idxs in INHERIT_FIELDS.items():
            if field == 'item':
                if b.get('item') and ('item', 0) not in inherited:
                    prev['item'] = b['item']
                continue
            vals = b.get(field)
            if not isinstance(vals, (list, tuple)):
                continue
            if any(i < len(vals) and vals[i] for i in idxs):
                prev[field] = list(vals)

        # --- 更新 pool_times: 記錄該池的入池時間 (含繼承值) ---
        if pool and b.get('pool_time'):
            pool_times[pool] = b['pool_time']

    # --- 小型管/通用: 奇數番(1-indexed)=0-indexed偶數, 入池時間参照下一偶數番 ---
    for bi in sorted(bands.keys()):
        b = bands[bi]
        if not isinstance(b, dict):
            continue
        if bi % 2 != 0:  # 0-indexed odd = 1-indexed even, skip
            continue
        pool = b.get('steam_pool')
        if pool and not b.get('pool_time'):
            for bj in range(bi + 1, len(bands)):
                nb = bands.get(bj)
                if not isinstance(nb, dict):
                    continue
                if nb.get('steam_pool') == pool and nb.get('pool_time'):
                    b['pool_time'] = nb['pool_time']
                    b.setdefault('inherited', []).append(('pool_time', 0))
                    log.info('pool_time odd-band backfill: band %d pool=%s pool_time=%s from band %d', bi, pool, nb['pool_time'], bj)
                    break

    return bands


def _dig(cell):
    import re
    m = re.search(r'\d+', cell or '')
    return m.group(0) if m else ''


def _small_cell(row, i):
    return row[i] if i < len(row) else ''


def _valid_range(d, lo, hi):
    if not d:
        return ''
    try:
        v = int(d)
    except (TypeError, ValueError):
        return ''
    return d if lo <= v <= hi else ''


def _parse_small_rows(r1, r2, r3):
    """Fixed-column parser for a 小型 band's 3 rows (23-col wide table).

    Layout: col0=番次 1=品項 2=管模 3-8=模具6 9-12=轉速 13=蒸養池
            21=溫度 22=階段 (per row: R1=溫度1/階段1 ... R3=溫度3/階段3)
    R2: col3=離心開始~結束, col9-12=時間4.
    Values are range-validated to drop OCR 幻覺 that leaks digits from other
    cells (e.g. a cent time landing in the temps column).
    """
    b = {'fan': '', 'item': '', 'molds': [''] * 6, 'centrifuge': ('', ''),
         'speeds': [''] * 4, 'speed_times': [''] * 4, 'steam_pool': '',
         'pool_time': '', 'temps': [''] * 3, 'stages': [''] * 3,
         'arrange': [], 'c14': [], 'c15': []}
    b['fan'] = _dig(_small_cell(r1, 0))
    b['item'] = normalize_item(_small_cell(r1, 1))
    for k in range(6):
        b['molds'][k] = _dig(_small_cell(r1, 3 + k))
    for k in range(4):
        d = _dig(_small_cell(r1, 9 + k))
        b['speeds'][k] = _valid_range(d, 100, 1400)
    pool_cell = _small_cell(r1, 13)
    nums = re.findall(r'\d+', pool_cell)
    if nums:
        if re.search(r'\d{4}', pool_cell):
            m = re.search(r'\d{4}', pool_cell)
            b['steam_pool'] = nums[0]
            if _valid_range(m.group(0), 600, 2359):
                b['pool_time'] = m.group(0)
        elif len(nums) >= 3 and len(nums[1]) == 2 and len(nums[2]) == 2:
            b['steam_pool'] = nums[0]
            hhmm = nums[1] + nums[2]
            if _valid_range(hhmm, 600, 2359):
                b['pool_time'] = hhmm
        else:
            b['steam_pool'] = nums[0]
    for k in range(4):
        d = _dig(_small_cell(r2, 9 + k))
        b['speed_times'][k] = _valid_range(d, 1, 20)
    cent_cell = _small_cell(r2, 3)
    cents = re.findall(r'\d{4}', cent_cell)
    if cents:
        b['centrifuge'] = (cents[0], cents[1] if len(cents) > 1 else '')
    elif cent_cell:
        ns = re.findall(r'\d+', cent_cell)
        if len(ns) >= 2:
            b['centrifuge'] = (ns[0], ns[1])
    for i, row in ((0, r1), (1, r2), (2, r3)):
        b['temps'][i] = _valid_range(_dig(_small_cell(row, 21)), 1, 150)
        b['stages'][i] = _valid_range(_dig(_small_cell(row, 22)), 1, 150)
    return b


def parse_small_band(row1, row2, row3):
    """Parse one 小型 band from its 3 markdown sub-rows (R1/R2/R3).

    Uses fixed 23-column layout when available, else falls back to the
    anchor-based scan (locate 管模 label and walk columns).
    Returns band dict (molds list len 6, speeds/times len 4, temps/stages len 3).
    """
    import re
    if len(row1) >= 14 and '模' in _small_cell(row1, 2) or ('模' in _small_cell(row1, 0)):
        b = _parse_small_rows(row1, row2, row3)
        if sum(1 for m in b['molds'] if m) or b['item'] or b['centrifuge'][0]:
            return b
    b = {'fan': '', 'item': '', 'molds': [''] * 6, 'centrifuge': ('', ''),
         'speeds': [''] * 4, 'speed_times': [''] * 4, 'steam_pool': '',
         'pool_time': '', 'temps': [''] * 3, 'stages': [''] * 3,
         'arrange': [], 'c14': [], 'c15': []}
    if not row1:
        return b

    b['fan'] = _dig(row1[0])

    # Find "模/管" label position first — anchors item (cell right before it), same
    # fix as parse_mid_table(): a fixed index for 品項 breaks whenever this fallback's
    # column count shifts (it only runs after the fixed-layout check already failed).
    mold_idx = -1
    for j, c in enumerate(row1):
        if '模' in c or '管' in c:
            mold_idx = j
            break

    item_idx = mold_idx - 1 if mold_idx >= 1 else 1
    b['item'] = normalize_item(row1[item_idx] if item_idx < len(row1) else '')

    if mold_idx >= 0:
        after = row1[mold_idx + 1:]
        for k in range(6):
            if k < len(after):
                b['molds'][k] = _dig(after[k])
        for k in range(6, 10):
            if k < len(after):
                d = _dig(after[k])
                b['speeds'][k - 6] = _valid_range(d, 100, 1400)
        for c in after[10:]:
            nums = re.findall(r'\d+', c)
            if not nums:
                continue
            m = re.match(r'^\s*(\d)\s*$', c)
            if m:
                b['steam_pool'] = m.group(1)
                break
            if re.search(r'\d\s*[:~．.]?\s*\d\s*\d', c) or len(nums) >= 2:
                b['steam_pool'] = nums[0]
                tm = re.findall(r'\d{1,2}', c)[:4]
                if len(tm) >= 2:
                    hhmm = tm[0].zfill(2) + tm[1].zfill(2)
                    b['pool_time'] = hhmm if _valid_range(hhmm, 600, 2359) else ''
                break

    if len(row2) > 1:
        cent = []
        for c in row2:
            for n in re.findall(r'\d{4}', c):
                if 600 <= int(n) <= 2359:
                    cent.append(n)
        b['centrifuge'] = (cent[0] if cent else '', cent[1] if len(cent) > 1 else '')
        tm = []
        for c in row2:
            if re.search(r'\d{4}', c):
                continue
            for n in re.findall(r'\d{1,2}', c):
                if 1 <= int(n) <= 20:
                    tm.append(n)
        b['speed_times'] = (tm + [''] * 4)[:4]

    for ri, row in ((0, row1), (1, row2), (2, row3)):
        digit_cells = [c for c in (row or []) if c is not None and _dig(c)]
        if len(digit_cells) >= 2:
            b['temps'][ri] = _valid_range(_dig(digit_cells[-2]), 1, 150)
            b['stages'][ri] = _valid_range(_dig(digit_cells[-1]), 1, 150)

    return b


def _md_data_rows(md):
    """Extract markdown table data rows as cell lists (skip header/separator)."""
    lines = [l for l in md.split('\n') if l.startswith('|')]
    parsed = [[c.strip() for c in l.strip('|').split('|')] for l in lines]
    out = []
    for row in parsed:
        if any('---' in c for c in row):
            continue
        if sum(1 for c in row if _dig(c)) >= 2 or sum(1 for c in row if '模' in c or '時' in c) >= 1:
            out.append(row)
    return out


def _small_crop(img, x0, x1, y0, y1, binarize=True, scale=2, thr=205):
    import numpy as np
    y1 = min(y1, img.shape[0])
    x1 = min(x1, img.shape[1])
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if binarize:
        _, g = cv2.threshold(g, thr, 255, cv2.THRESH_BINARY)
    if scale != 1:
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def ocr_small_band(pdf_path, page_index, y0, y1, x0=30, x1=1500, scale=2, binarize=True):
    """OCR one 小型 band strip (full width, band height) and parse its fields.

    Returns band dict, or {} on failure. One API call per band.
    """
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    crop = _small_crop(img, x0, x1, y0, y1, binarize=binarize, scale=scale)
    if crop is None:
        return {}
    md = ocr_image(crop)
    log.info('ocr_small_band %s p%d band_y=(%d,%d) -> %s', os.path.basename(pdf_path),
             page_index + 1, y0, y1, 'ok' if md else 'FAIL')
    if not md:
        return {}
    data_rows = _md_data_rows(md)
    if not data_rows:
        return {}
    r1 = data_rows[0] if len(data_rows) >= 1 else []
    r2 = data_rows[1] if len(data_rows) >= 2 else []
    r3 = data_rows[2] if len(data_rows) >= 3 else []
    return parse_small_band(r1, r2, r3)


def ocr_small_strip(pdf_path, page_index, y0, y1, x0=30, x1=1500, scale=2, thr=205, raw=False):
    """OCR a horizontal strip spanning several 小型 bands; parse into per-band dicts.

    Returns dict {band_offset: band_dict}, band_offset relative to the strip's
    first band. A strip containing N bands produces N dicts (some may be {}).
    If raw=True, returns the raw markdown string instead.
    """
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    crop = _small_crop(img, x0, x1, y0, y1, binarize=True, scale=scale, thr=thr)
    if crop is None:
        return {} if not raw else ''
    md = ocr_image(crop)
    log.info('ocr_small_strip %s p%d strip_y=(%d,%d) -> %s', os.path.basename(pdf_path),
             page_index + 1, y0, y1, 'ok' if md else 'FAIL')
    if raw:
        return md or ''
    if not md:
        return {}
    return parse_small_strip(md)


def parse_small_strip(md, n_bands=None):
    """Split strip markdown rows into per-band blocks and parse each band.

    A band block starts at the row containing the 管模 label (R1). The following
    rows are that band's R2/R3. Falls back to fixed 3-row grouping when no
    管模 anchors are found.
    """
    data_rows = _md_data_rows(md)
    if not data_rows:
        return {}
    anchors = [i for i, r in enumerate(data_rows) if any('模' in c for c in r)]
    blocks = []
    if anchors:
        for k, a in enumerate(anchors):
            end = anchors[k + 1] if k + 1 < len(anchors) else len(data_rows)
            blocks.append(data_rows[a:min(end, a + 3)])
    else:
        blocks = [data_rows[i:i + 3] for i in range(0, len(data_rows), 3)]
    out = {}
    for k, blk in enumerate(blocks):
        r1 = blk[0] if len(blk) >= 1 else []
        r2 = blk[1] if len(blk) >= 2 else []
        r3 = blk[2] if len(blk) >= 3 else []
        out[k] = parse_small_band(r1, r2, r3)
    return out


def ocr_small_field(pdf_path, page_index, x0, x1, y0, y1, kind, scale=3, thr=205):
    """OCR one narrow 小型 field crop; returns raw markdown (or '')."""
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    crop = _small_crop(img, x0, x1, y0, y1, binarize=True, scale=scale, thr=thr)
    if crop is None:
        return ''
    md = ocr_image(crop)
    log.info('ocr_small_field %s p%d %s box=(%d,%d,%d,%d) -> %s', os.path.basename(pdf_path),
             page_index + 1, kind, x0, y0, x1 - x0, y1 - y0, 'ok' if md else 'FAIL')
    return md or ''


def _extract_numbers(text, lo=None, hi=None):
    import re
    out = []
    for n in re.findall(r'\d{1,4}', text):
        v = int(n)
        if lo is not None and v < lo:
            continue
        if hi is not None and v > hi:
            continue
        out.append(n)
    return out


def _fill_small_field(b, kind, md):
    """Fill a band dict field from a narrow-crop markdown read."""
    if not md or not b:
        return b
    import re
    rows = _md_data_rows(md)
    cells = [c for row in rows for c in row]
    if kind == 'cent':
        ns = _extract_numbers(md, 500, 2400)
        if len(ns) >= 2:
            b['centrifuge'] = (ns[0], ns[1])
        elif len(ns) == 1:
            b['centrifuge'] = (ns[0], b['centrifuge'][1])
    elif kind == 'speeds':
        ns = [c for c in cells if c and re.fullmatch(r'\d{2,4}', c)][:4]
        if len(ns) >= 2:
            b['speeds'] = (ns + [''] * 4)[:4]
    elif kind == 'times':
        ns = [c for c in cells if c and re.fullmatch(r'\d{1,2}', c)][:4]
        if len(ns) >= 2:
            b['speed_times'] = (ns + [''] * 4)[:4]
    elif kind == 'pool':
        ns = _extract_numbers(md, 1, 99)
        if ns:
            b['steam_pool'] = ns[0]
    elif kind == 'temps':
        vals = _extract_numbers(md, 1, 150)
        if len(vals) >= 3:
            b['temps'] = vals[:3]
    elif kind == 'stages':
        vals = _extract_numbers(md, 1, 150)
        if len(vals) >= 3:
            b['stages'] = vals[:3]
    elif kind == 'item':
        s = ''
        for row in rows:
            for c in row:
                if re.match(r'^\d{2,4}', c) and '模' not in c and '時' not in c:
                    s = c
                    break
            if s:
                break
        if s:
            b['item'] = s
    return b


def _fullness(b):
    if not b:
        return 0
    n = 0
    for v in b.values():
        if isinstance(v, (list, tuple)):
            n += sum(1 for x in v if x)
        elif v:
            n += 1
    return n


def _merge_fullest(a, b):
    """Combine two band dicts from different reads; prefer the fuller one.

    The fuller read is the base; the other only fills keys the base lacks.
    This protects against one read returning merged/garbled values (page-bottom
    strips merge mold cells) while still filling gaps from the weaker read.
    """
    if not a and not b:
        return None
    fa, fb = _fullness(a), _fullness(b)
    if fa >= fb:
        base, other = a, b
    else:
        base, other = b, a
    out = dict(base or {})
    for k, v in (other or {}).items():
        cur = out.get(k)
        if isinstance(cur, (list, tuple)):
            ov = v if isinstance(v, (list, tuple)) else []
            cur_l = list(cur)
            for i in range(min(len(cur_l), len(ov))):
                if not cur_l[i] and ov[i]:
                    cur_l[i] = ov[i]
            out[k] = tuple(cur_l) if isinstance(cur, tuple) else cur_l
        elif cur in ('', None):
            out[k] = v
    return out


def ocr_small_page(pdf_path, page_index, rows, cols, field_crops=False):
    """Full 小型 page pipeline: 3-band strips + per-band full-width retry.

    Pipeline:
      1. Strips of 3 bands, full width, binarized.
      2. Per-band full-width crop (also binarized) for every band.
      3. Each band = _merge_fullest(strip_read, band_read) — the fuller read
         wins, the other only fills gaps (Mistral is nondeterministic, so both
         reads can succeed or fail on different calls).
      4. Optional per-field narrow crops (field_crops=True). These HALLUCINATE
         on the small form's 53-68px cells, so they are OFF by default.

    Args:
        rows: [(y0, y1)...] band rows.
        cols: SMALL_COLS column x-boundaries list (kept for the field-crop path).
    Returns:
        {band_index: band_dict}
    """
    n = len(rows)
    strip_reads = {}
    group = []
    for bi in range(n):
        group.append(bi)
        if len(group) == 3 or bi == n - 1:
            y0 = rows[group[0]][0]
            y1 = rows[group[-1]][1]
            got = ocr_small_strip(pdf_path, page_index, y0, y1)
            for k, b in got.items():
                strip_reads[group[k]] = b
            group = []

    bands = {}
    for bi in range(n):
        y0, y1 = rows[bi]
        band_read = ocr_small_band(pdf_path, page_index, y0, y1)
        bands[bi] = _merge_fullest(strip_reads.get(bi), band_read) or {}

    if field_crops:
        field_boxes = {}
        for bi in range(n):
            y0 = rows[bi][0]
            field_boxes[bi] = {
                'item': (cols[1], cols[2], y0, y0 + 60),
                'molds': (cols[3], cols[9], y0, y0 + 60),
                'cent': (cols[3], cols[9], y0 + 60, y0 + 120),
                'speeds': (cols[9], cols[13], y0, y0 + 60),
                'times': (cols[9], cols[13], y0 + 60, y0 + 120),
                'pool': (cols[13], cols[14], y0, y0 + 180),
                'temps': (cols[21], cols[22], y0, y0 + 180),
                'stages': (cols[22], cols[23], y0, y0 + 180),
            }
        for bi in range(n):
            b = bands.get(bi) or {}
            y0 = rows[bi][0]
            for kind, (x0, x1, ya, yb) in field_boxes[bi].items():
                need = False
                if kind == 'cent':
                    need = not (b.get('centrifuge') or ('', ''))[0]
                elif kind == 'speeds':
                    need = sum(1 for s in b.get('speeds', []) if s) < 2
                elif kind == 'times':
                    need = sum(1 for s in b.get('speed_times', []) if s) < 2
                elif kind == 'pool':
                    need = not b.get('steam_pool')
                elif kind == 'temps':
                    need = sum(1 for s in b.get('temps', []) if s) < 2
                elif kind == 'stages':
                    need = sum(1 for s in b.get('stages', []) if s) < 2
                elif kind == 'item':
                    need = not b.get('item')
                if not need:
                    continue
                md = ocr_small_field(pdf_path, page_index, x0, x1, ya, yb, kind)
                b = _fill_small_field(b, kind, md)
                bands[bi] = b

    for bi in range(n):
        b = bands.setdefault(bi, {})
        if not b.get('fan'):
            b['fan'] = str(bi + 1)
        if not b.get('arrange') and b.get('molds'):
            b['arrange'] = list(b['molds'])
    return bands
