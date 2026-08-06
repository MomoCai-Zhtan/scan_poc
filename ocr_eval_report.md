# OCR AutoFill 評估摘要報告

**專案**: 離心製管掃描輸入工具 (OCR WebApp MVP)
**日期**: 2026-08-06
**範圍**: OCR API 流程優化 + LLM 混合方案評估 + Workflow Bug 審查

---

## 1. 現況性能基線

| 表單類型 | 測試樣本 | 準確率 | 主要誤差來源 |
|----------|----------|--------|-------------|
| 中型 (完整墨跡) | 1150702.pdf | 90.3% (65/72) | 模具編號偶爾誤讀 |
| 中型 (稀少墨跡) | 1150729.pdf | 93.1% (67/72) | C14/C15 空白 |
| 小型 | 1150702.pdf | 59.3% (185/312) | 淡墨欄 (轉速/時間/溫度/階段) 無墨 |
| **全基線 (21 份)** | 2371 欄位 | **81.1%** (1923/2371) | item 33, cent 95, speeds 103, times 111 |

**結論**: 核心欄位 (番次/品項/模具/離心時間/轉速/蒸養池) 已達可用水準 (85-95%)，**瓶頸在於淡墨手寫欄位** (C14/C15/轉速/時間)。

---

## 2. Workflow Bug 與死碼審查

### 2.1 已確認的 Bug

| 嚴重度 | 位置 | 問題 | 影響 |
|--------|------|------|------|
| **中** | `index.html:1024-1034` | 無 AbortController，快速翻頁時前頁 OCR 回應會覆蓋當前狀態 | 使用者看到錯誤的 band 資料 |
| **中** | `ocrx.py:290-291` | `parse_mid_table()` 用固定 index 13/14 讀 C14/C15，OCR 表格位移時讀到鄰欄 | 中型表單 C14/C15 誤讀 |
| **低** | `app.py:7` | `import re` 未使用 | 無功能影響 |
| **低** | `ocrx.py:139` | `import re` 在函數內部重複 import | 效能開銷可忽略 |

### 2.2 死碼 (Dead Code)

| 程式碼 | 狀態 | 建議 |
|--------|------|------|
| `ocrx.py:_extract_c14c15()` (L132-145) | 未被呼叫 | 移除 (已被 `_extract_2digit` 取代) |
| `ocrx.py:ocr_c14c15_crop()` (L328-351) | 僅在 `analysis.py:_retry_c14c15` 呼叫 | **保留** — 這是 C14/C15 retry 的核心路徑 |
| `app.py:_page_cache_load` 無版本號 | 功能缺失 | 加入 `_meta.version`，避免 auto_fields schema 變更後使用舊快取 |

### 2.3 架構問題

| 問題 | 建議 |
|------|------|
| `COLLECTIONS` 全域 dict，重啟遺失 | 寫入 SQLite 或 `shelve` |
| 單一 1076 行 HTML 內嵌 CSS/JS | 拆成 `style.css` + `app.js` |
| `recomputeDerived()` 無 debounce | 加入 100ms debounce 減少 DOM 操作 |

---

## 3. 方案評估：純 OCR vs LLM 混合

### 3.1 純 OCR 方案 (維持現有 Mistral OCR)

**優點**:
- 成本低: ~$0.003-0.006/頁
- 延遲可預測: 單頁 ~3-5s
- 無新增依賴

**限制**:
- C14/C15 淡墨欄 = **硬傷** (任何 OCR 都無法從無墨影像讀出數字)
- 狹窄 crop (53-68px) → Mistral 容易 hallucinate 或回傳空白
- 欄位錯位 (品項讀到鄰欄) → 語法正確但語意錯誤，難以偵測

**預期天花板**: **85-88%** (已接近純 OCR 極限)

### 3.2 LLM 混合方案 (LLM-as-Judge)

**優點**:
- C14/C15 淡墨復活: LLM vision model 可從極低墨跡推斷數字
- 語意驗證: LLM 可根據詞彙表 + 鄰番一致性糾正欄位錯位
- 彈性觸發: 只對「不確定」欄位呼叫，控制成本

**限制**:
- 成本增加: ~$0.01-0.03/頁 (只在有問題頁面觸發)
- 延遲: +2-5s/LLM call (可並行化)
- LLM 幻覺風險: 需要嚴格的 prompt engineering + JSON mode

**預期天花板**: **90-93%** (接近人工輸入水準)

### 3.3 方案比較矩陣

| 維度 | 純 OCR | LLM 混合 | 備註 |
|------|--------|----------|------|
| **準確率** | 81-88% | 90-93% | LLM 主要提升 C14/C15 + item 欄位 |
| **Cost/頁** | $0.003-0.006 | $0.01-0.035 | LLM 只在不確定時觸發 |
| **延遲/頁** | 3-5s | 5-10s | 可並行 LLM call |
| **實作複雜度** | - | 中 | 需新模組 + prompt 設計 |
| **維護成本** | 低 | 中 | LLM prompt 可能需要隨模型更新調整 |
| **穩定性** | 高 | 中 | 依賴外部 API (Mistral + OpenAI/Anthropic) |
| **可解釋性** | 中 | 低 | LLM 決策不如 OCR 規則透明 |

---

## 4. 建議決策

### 4.1 短期 (本週) — 純 OCR 優化

**理由**: 當前 81.1% 已達可用水準，優先解決 workflow bug 和 UX 問題比提升 5% 準確率更有價值。

**行動項目**:
1. **Fix AbortController** (`index.html`): 翻頁時取消前頁 OCR 請求
2. **Fix C14/C15 固定 index bug** (`ocrx.py:290-291`): 改為動態錨定
3. **加入 per-band 快取**: 減少重複 OCR cost
4. **前端 debounce**: `recomputeDerived()` 加入 100ms debounce
5. **移除死碼**: `_extract_c14c15()`

**預期效果**: 穩定性提升，cost 降低 ~20%，無準確率提升。

### 4.2 中期 (下個月) — 評估 LLM 必要性

**觸發條件** (滿足任一則啟動):
- 使用者反馈「C14/C15 修正太繁瑣」
- 基線準確率停滯在 85% 以下
- 淡墨 PDF 占比 > 30%

**準備工作**:
- 建立 `llm_decisions.jsonl` 日誌格式
- 設計 LLM prompt template (C14/C15 + item 兩個场景)
- 評估 GPT-4o-mini vs Claude Haiku 的 cost/準確率權衡

### 4.3 长期 — 結構性改善

| 項目 | 說明 | 優先級 |
|------|------|--------|
| 前端模組化 | 拆 CSS/JS，加入測試 | 高 |
| 後端持久化 | COLLECTIONS 寫入 SQLite | 中 |
| 增量快取 | per-band 快取 + 版本號 | 中 |
| CI 基線測試 | 自動跑 21 份 GT，threshold 75% | 高 |

---

## 5. 結論

**「單純靠 OCR API 辨識即可」是正確的策略**，原因：

1. **81.1% 已達可用水準**: 核心欄位 (番次/品項/模具/離心時間/轉速/蒸養池) 85-95%，剩餘誤差主要為淡墨手寫 (物理上無墨，任何 OCR 都無法解決)
2. **LLM 成本效益比不高**: 投入 ~$0.01-0.03/頁只換取 5-8% 準確率提升，且增加系統複雜度
3. **優先級應放在 UX**: 當前最痛的是 workflow bug (翻頁狀態覆蓋、固定 index bug) 和 UX (單一巨型 HTML、無 debounce)

**何時該 reconsider LLM**:
- 當使用者明确表示「C14/C15 修正太花時間」
- 當淡墨 PDF 成為主要使用場景
- 當 Mistral OCR 出現重大品質下降

---

## 6. 附錄：审查發現一覽

### Bug
- [ ] `index.html`: 加入 AbortController 防止翻頁狀態覆蓋
- [ ] `ocrx.py:290-291`: 修復 C14/C15 固定 index 讀取 bug
- [ ] `app.py:7`: 移除未使用 `import re`

### 死碼
- [ ] `ocrx.py:_extract_c14c15()`: 移除 (未被呼叫)
- [ ] `ocrx.py:139`: 移除函數內部 `import re` (檔案頂部已有)

### 改善建議
- [ ] `app.py`: COLLECTIONS 寫入 SQLite
- [ ] `index.html`: 拆分 CSS/JS，加入 debounce
- [ ] `app.py`: 快取加入版本號
- [ ] `analysis.py`: `parse_mid_table` 加入番次範圍約束
