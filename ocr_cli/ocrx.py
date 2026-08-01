# -*- coding: utf-8 -*-
"""Mistral OCR integration: send page image to Mistral OCR API, return markdown."""
import os, sys, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import httpx
import numpy as np

ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

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
        return None
    _, buf = cv2.imencode('.png', bgr)
    b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

    headers = {'Authorization': f'Bearer {OCR_API_KEY}', 'Content-Type': 'application/json'}
    data = {
        'model': OCR_MODEL,
        'document': {'type': 'image_url', 'image_url': f'data:image/png;base64,{b64}'},
        'include_image_base64': False,
    }
    resp = httpx.post(OCR_API_URL, headers=headers, json=data, timeout=120)
    if resp.status_code != 200:
        return None
    result = resp.json()
    pages_data = result.get('pages', [])
    if pages_data:
        return pages_data[0].get('markdown', '')
    return None


def ocr_page(pdf_path, page_index):
    """Send a single PDF page to Mistral OCR. Returns markdown string."""
    pages = st.render_pages(pdf_path, 200)
    img = pages[page_index]
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return ocr_image(bgr)


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
    return ocr_image(cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))


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
    return ocr_image(cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))


def _extract_c14c15(r1, col_idx):
    """Extract sub-row values from a C14 or C15 cell.

    C14/C15 cells contain 3 sub-rows of handwritten digits, either as a single
    digit (e.g. "60") or space-separated (e.g. "60 90 90" for 3 sub-rows).
    Returns list of up to 3 digit strings.
    """
    import re
    if col_idx >= len(r1):
        return []
    cell = r1[col_idx].strip()
    nums = re.findall(r'\d+', cell)
    return nums[:3]


def parse_mid_table(markdown):
    """Parse Mistral OCR markdown table into structured field values for medium form.

    Returns dict: {'fan': str, 'item': str, 'molds': [...], 'centrifuge': (start, end),
                   'speeds': [...], 'speed_times': [...], 'steam_pool': str}
    per band index.
    """
    import re

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

        # 品項: cell 1 (strip "管模"), normalize to canonical GT form
        item = r1[1] if len(r1) > 1 else ''
        if '管模' in item:
            item = item.replace('管模', '').strip()
        item = normalize_item(item)

        # Find "管模" position to anchor mold extraction
        mold_label = -1
        for j, c in enumerate(r1):
            if '管模' in c:
                mold_label = j
                break

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
            'c14': _extract_c14c15(r1, 13),
            'c15': _extract_c14c15(r1, 14),
        }
        band_idx += 1
        i += 2

    return bands


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
