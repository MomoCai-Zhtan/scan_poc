# -*- coding: utf-8 -*-
"""概念驗證: AWS Textract Tables 模式 vs Mistral OCR 結構比較

因環境無 AWS 憑證,此腳本使用模擬回應展示 Textract 輸出結構,
並與 Mistral OCR 實際輸出進行對比分析。

執行: python ocr_cli/verify_textract_concept.py
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure as st
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_SAMPLE = os.path.join(ROOT, '1150729.pdf')
PAGE_IDX = 1  # p2

COST_MISTRAL_PER_PAGE = 0.001   # USD (估算)
COST_TEXTRACT_PER_PAGE = 0.015  # USD (Tables 模式, 1-3 頁 $0.015/頁)
COST_TEXTRACT_LARGE = 0.050     # USD (>3 頁批次)


def render_page():
    """Render p2 for comparison."""
    pages = st.render_pages(PDF_SAMPLE, 200)
    return pages[PAGE_IDX]


def mock_textract_tables_response(img_shape):
    """產生模擬 Textract Tables 回應,展示結構格式。"""
    h, w = img_shape[:2]
    return {
        'DocumentMetadata': {
            'Pages': 1,
            'DocumentId': 'mock-textract-doc'
        },
        'Blocks': [
            {
                'BlockType': 'TABLE',
                'Confidence': 98.5,
                'Geometry': {
                    'BoundingBox': {'Width': 0.95, 'Height': 0.85, 'Left': 0.02, 'Top': 0.05},
                    'Polygon': [
                        {'X': 0.02, 'Y': 0.05}, {'X': 0.97, 'Y': 0.05},
                        {'X': 0.97, 'Y': 0.90}, {'X': 0.02, 'Y': 0.90}
                    ]
                }
            },
            {
                'BlockType': 'CELL',
                'Confidence': 92.0,
                'RowIndex': 1,
                'ColumnIndex': 1,
                'RowSpan': 1,
                'ColumnSpan': 1,
                'Geometry': {
                    'BoundingBox': {'Width': 0.06, 'Height': 0.04, 'Left': 0.02, 'Top': 0.10},
                },
                'Text': '1'
            },
            {
                'BlockType': 'CELL',
                'Confidence': 95.0,
                'RowIndex': 1,
                'ColumnIndex': 2,
                'RowSpan': 2,
                'ColumnSpan': 1,
                'Geometry': {
                    'BoundingBox': {'Width': 0.08, 'Height': 0.08, 'Left': 0.08, 'Top': 0.10},
                },
                'Text': '800'
            },
            {
                'BlockType': 'CELL',
                'Confidence': 88.0,
                'RowIndex': 2,
                'ColumnIndex': 2,
                'RowSpan': 1,
                'ColumnSpan': 1,
                'Geometry': {
                    'BoundingBox': {'Width': 0.02, 'Height': 0.03, 'Left': 0.08, 'Top': 0.14},
                },
                'Text': '3'
            },
            {
                'BlockType': 'CELL',
                'Confidence': 91.0,
                'RowIndex': 1,
                'ColumnIndex': 3,
                'RowSpan': 1,
                'ColumnSpan': 1,
                'Geometry': {
                    'BoundingBox': {'Width': 0.05, 'Height': 0.04, 'Left': 0.16, 'Top': 0.10},
                },
                'Text': '加料'
            },
            {
                'BlockType': 'CELL',
                'Confidence': 97.0,
                'RowIndex': 2,
                'ColumnIndex': 3,
                'RowSpan': 1,
                'ColumnSpan': 1,
                'Geometry': {
                    'BoundingBox': {'Width': 0.05, 'Height': 0.04, 'Left': 0.16, 'Top': 0.14},
                },
                'Text': '280'
            },
            {
                'BlockType': 'CELL',
                'Confidence': 85.0,
                'RowIndex': 1,
                'ColumnIndex': 12,
                'RowSpan': 1,
                'ColumnSpan': 1,
                'Geometry': {
                    'BoundingBox': {'Width': 0.04, 'Height': 0.08, 'Left': 0.70, 'Top': 0.10},
                },
                'Text': '4'
            },
            {
                'BlockType': 'CELL',
                'Confidence': 72.0,
                'RowIndex': 1,
                'ColumnIndex': 13,
                'RowSpan': 3,
                'ColumnSpan': 1,
                'Geometry': {
                    'BoundingBox': {'Width': 0.12, 'Height': 0.12, 'Left': 0.74, 'Top': 0.10},
                },
                'Text': '3 1 4'
            },
        ],
        'AnalyzeDocumentModelVersion': '3.0'
    }


def parse_textract_to_fields(response):
    """將 Textract cell-level output 轉為專案 auto_fields 結構。"""
    cells = [b for b in response.get('Blocks', []) if b.get('BlockType') == 'CELL']
    if not cells:
        return {}

    max_row = max(c.get('RowIndex', 0) for c in cells)
    max_col = max(c.get('ColumnIndex', 0) for c in cells)

    grid = {}
    for c in cells:
        ri = c.get('RowIndex', 0)
        ci = c.get('ColumnIndex', 0)
        key = (ri, ci)
        grid[key] = {
            'text': c.get('Text', ''),
            'conf': c.get('Confidence', 0),
            'row_span': c.get('RowSpan', 1),
            'col_span': c.get('ColumnSpan', 1),
            'geometry': c.get('Geometry', {}).get('BoundingBox', {}),
        }

    bands = {}
    band_idx = 0
    row_cursor = 1
    while row_cursor <= max_row:
        band_row_start = row_cursor
        band_row_end = min(row_cursor + 1, max_row + 1)
        row_cursor = band_row_end + 1

        b = {'fan': '', 'item': '', 'molds': [''] * 4,
             'centrifuge': ('', ''), 'speeds': [''] * 4,
             'speed_times': [''] * 4, 'steam_pool': '',
             'arrange': '', 'c14': [], 'c15': []}

        for (ri, ci), cell in grid.items():
            if not (band_row_start <= ri < band_row_end):
                continue
            text = cell['text']
            conf = cell['conf']

            if ci == 1:
                b['fan'] = text
            elif ci == 2:
                if cell['row_span'] >= 2:
                    b['item'] = text
                else:
                    b['molds'][0] = text
            elif ci == 3:
                if ri == band_row_start:
                    b['speeds'][0] = text if conf > 80 else ''
                else:
                    b['speed_times'][0] = text if conf > 80 else ''
            elif ci == 12:
                b['steam_pool'] = text
            elif ci == 13:
                b['arrange'] = text.split()

        bands[band_idx] = b
        band_idx += 1

    return bands


def compare_structures(mistral_bands, textract_bands):
    """比較兩個 OCR 引擎的輸出結構差異。"""
    report = []
    report.append("=" * 60)
    report.append("結構比較: Mistral OCR vs AWS Textract")
    report.append("=" * 60)

    report.append("\n[輸出格式]")
    report.append(f"  Mistral:  markdown 文字 → 自行 parse (字串處理)")
    report.append(f"  Textract: cell-level JSON → 直接映射 (結構化)")

    report.append("\n[信心度分數]")
    report.append(f"  Mistral:  無 (只有成功/失敗)")
    report.append(f"  Textract:  每 cell 有 Confidence (0-100)")

    report.append("\n[座標資訊]")
    report.append(f"  Mistral:  無 bounding box")
    report.append(f"  Textract:  每 cell 有 BoundingBox + Polygon")

    report.append("\n[合併單元]")
    report.append(f"  Mistral:  需自行推測 rowSpan/colSpan")
    report.append(f"  Textract:  直接回傳 RowSpan/ColumnSpan")

    report.append("\n[錯誤處理]")
    report.append(f"  Mistral:  markdown 解析失敗 →  Entire band 失敗")
    report.append(f"  Textract:  單一 cell 低 confidence → 可單獨 retry")

    report.append("\n[解析複雜度]")
    report.append(f"  Mistral:  高 (regex + 字串處理)")
    report.append(f"  Textract:  低 (直接 cell → field mapping)")

    report.append("\n[本次概念驗證結果]")
    report.append(f"  Mistral bands parsed: {len(mistral_bands)}")
    report.append(f"  Textract bands parsed: {len(textract_bands)}")

    m_fields = sum(1 for b in mistral_bands.values() if any(b.get(k) for k in ['item', 'molds', 'speeds']))
    t_fields = sum(1 for b in textract_bands.values() if any(b.get(k) for k in ['item', 'molds', 'speeds']))
    report.append(f"  Mistral bands with data: {m_fields}/{len(mistral_bands)}")
    report.append(f"  Textract bands with data: {t_fields}/{len(textract_bands)}")

    low_conf_cells = [
        c for c in mock_textract_tables_response((0, 0))['Blocks']
        if c.get('BlockType') == 'CELL' and c.get('Confidence', 100) < 80
    ]
    report.append(f"  Textract low-confidence cells (<80): {len(low_conf_cells)}")

    report.append("\n[成本比較 (單頁)]")
    report.append(f"  Mistral OCR: ${COST_MISTRAL_PER_PAGE:.3f} (1-2 API calls)")
    report.append(f"  Textract:    ${COST_TEXTRACT_PER_PAGE:.3f} (1 API call, Tables)")
    report.append(f"  倍數:        {COST_TEXTRACT_PER_PAGE / COST_MISTRAL_PER_PAGE:.1f}x")

    report.append("\n[延遲比較 (單頁)]")
    report.append(f"  Mistral OCR: ~2-4s (雲端 API)")
    report.append(f"  Textract:    ~1-3s (雲端 API, 通常更快)")
    report.append(f"  倍數:        ~0.5-0.7x (Textract 稍快)")

    report.append("\n[結論]")
    report.append("  Textract 的結構化輸出可大幅降低解析層複雜度,")
    report.append("  且 confidence score 對低信心欄位自動觸發 retry 非常有價值。")
    report.append("  但成本高 15x,且需重寫 ocrx.py 全部解析層。")
    report.append("  建議: 若 Mistral 準確率停滯在 85% 以下,再考慮迁移。")
    report.append("=" * 60)
    return "\n".join(report)


def main():
    print("載入 PDF 頁面...")
    img = render_page()
    print(f"頁面尺寸: {img.shape[1]}x{img.shape[0]}")

    print("\n執行 Mistral OCR (使用快取或即時辨識)...")
    t0 = time.time()
    try:
        import ocrx
        md = ocrx.ocr_page(PDF_SAMPLE, PAGE_IDX)
        mistral_time = time.time() - t0
        print(f"  Mistral OCR 耗時: {mistral_time:.1f}s")
        if md:
            mistral_bands = ocrx.parse_mid_table(md)
            print(f"  解析出 {len(mistral_bands)} 個 band")
        else:
            print("  Mistral OCR 失敗,使用空結果")
            mistral_bands = {}
    except Exception as e:
        print(f"  Mistral OCR 錯誤: {e}")
        mistral_bands = {}

    print("\n模擬 Textract Tables 回應...")
    textract_resp = mock_textract_tables_response(img.shape)
    textract_bands = parse_textract_to_fields(textract_resp)
    print(f"  Textract 解析出 {len(textract_bands)} 個 band")

    print("\n" + compare_structures(mistral_bands, textract_bands))

    print("\n[Textract 概念驗證完成]")
    print("注意: 本驗證使用模擬回應,實際效果需在有 AWS 憑證的環境中驗證。")


if __name__ == '__main__':
    main()
