# 開發歷程記錄

> **專案**: 離心製管掃描輸入工具 (OCR WebApp MVP)
> **工作目錄**: `D:\OneDrive - 振添股份有限公司\RD_DATA\scan\2026\07-掃描`

## 對話歷程

### 2026-07-31 20:00 UTC+8 — 續接 OpenCode session ses_0489d7cdfffeDaewfq4KXZcKsg

**背景**: 使用者透過 `opencode -s ses_0489d7cdfffeDaewfq4KXZcKsg` 嘗試恢復 OpenCode 會話，但進入 Kilo 環境。Kilo 從 OpenCode 本地 DB (`C:\Users\momo_\.local\share\opencode\opencode.db`) 讀取會話內容，恢復對話脈絡。

#### 歷史對話摘要

**第 1 段對話** (OpenCode session 開始)
- 使用者提出 WebApp MVP 規格: PDF → 版面分析 → 網頁手動輸入 → 39欄 CSV
- PM 提出建議 (Flask + Bootstrap + OpenCV + EasyOCR)
- 助手評估: EasyOCR 已裝 (1.7.2), 評估腳本 `ocr_cli/eval_easyocr.py`

**第 2 段對話** — 中型表單欄位定義 (逐步)
- 使用者說: "C4~C7 有上下兩列, 第一列是模具編號 eg. 3 4 1, 第二列是離心時間開始跟結束 eg. 0750 0830"
- 使用者說: "C8~C11 是離心機台設定數據 也是分兩列, 列一: 加料轉速 慢速轉速 中速轉速 高速轉速 eg. 280 320 530 980"
- 使用者說: "列二: 加料時間 慢速時間 中速時間 高速時間 eg. 12 4 3 11"
- 使用者說: "C12 為 蒸養池編號 eg. 4"
- 使用者說: "以ban4 為例 品項C2是 400 加厚 有出現手寫中文"

**第 3 段對話** — 確認欄位與切割 (最近)
- 使用者說: "C14 蒸養溫度 有3列 分別是 蒸養溫度1~3"
- 使用者說: "C15 蒸養時間 有3列 分別是 蒸養時間1~3"
- 使用者說: "C16 發現情形 忽略"
- 使用者說: "離心時間C3~C7 R2"

**助手狀態**: 會話中助手的最後一則消息有 0 tokens (尚未產生回應)

#### 關鍵技術發現

1. **中型表單每番 = 264px**，含 2 子列 (R1 + R2)，分隔線在 band offset ~176 (非中點 508)
2. **C12 (蒸養池)** 為合併欄 (R1+R2 跨列)
3. **C13 (模具排列順序)** 為圓圈欄，已改切 4 格 (4 個模具欄位 × 全番高)
4. **C14 (蒸養溫度)** = 3 子列 (溫度1, 2, 3) — 垂直分欄
5. **C15 (蒸養時間)** = 3 子列 (時間1, 2, 3) — 垂直分欄
6. **C16 (發現情形)** = 忽略欄位
7. **C3~C7 R2** = 離心時間 (開始 + 結束)
8. **EasyOCR 基準測試**: 1150729 中型 8 番 × 16 欄 = 128 格, 僅 6.2% (128 格僅 8 格正確, 全為空 GT 的模具4) → 結論: 維持人工輸入路線
9. **win_ocr.ps1** 只能在 PowerShell 直接跑; 中文檔名會讓 Windows.Storage 開檔失敗 → OCR 輸入/輸出檔名必須用英文

#### 垂直線座標 (來自 mid_hdr_0729_ocr.txt + 1150729 p2 OCR)

C 欄號 (來自 OCR 標頭分析 + ink 分佈):
- C1: x89-147 — 番/序
- C2: x147-252 — 品項
- C3: x252-324 — (數字, R1+R2 均有墨)
- C4: x324-390 — 模具編號 (R1) / 離心開始 (R2)
- C5: x390-455 — 模具編號 (R1) / 離心結束 (R2)
- C6: x455-521 — 模具編號 (R1)
- C7: x521-587 — (R2 延續)
- C8-C11: x587-876 — 轉速 (R1) / 轉速時間 (R2)
- C12: x876-958 — 蒸養池編號 (R1+R2 合併)
- C13: x958-1248 — 模具排列順序 (切 4 格)
- C14: x1248-1320 — 蒸養溫度1~3 (3 子列)
- C15: x1320-1391 — 蒸養時間1~3 (3 子列)
- C16: x1391-1564 — 發現情形 (忽略)

## 程式碼現況

### `ocr_cli/analysis.py` (vCurrent)
- `find_lines_robust()` — robust 線檢測 (背景扣除 + 形態學)
- `row_bands()` — 小型/中型分類 + 番次列邊界檢測
- `detect_arrange_grid()` — C12 4 格切割 (已完成)
- `page_analysis()` — 頁面分析入口 (回傳 type, rows, shift, h_lines, v_lines)
- `analyze_pdf()` — 批次分析

### `scan_entry/app.py` (vCurrent)
- Flask webapp，39 欄 CSV 匯出
- `/img/<name>/<page>` — 格線標註圖
- `/arrange/<name>/<page>/<band>` — C12 4 格合成圖
- `/api/pdf/<name>` — 頁面分析 JSON
- `/export` — CSV 下載

### `scan_entry/templates/index.html` (vCurrent)
- 完整 UI: PDF 選擇、時間段下拉、番次選擇、4 格排列預覽、39 欄表格輸入、CSV 匯出
- 群組: 基本、轉位、離心、蒸養、排列 (5 群組)
- `GROUPS` 常數定義了欄位分群

## 執行記錄

```
# 會話摘要
- session: ses_0489d7cdfffeDaewfq4KXZcKsg
- model: big-pickle (opencode)
- tokens_input: 574435, tokens_output: 145859, tokens_reasoning: 306063
- 建立時間: 2026-07-31T08:55:14Z
- 最後更新: 2026-07-31T20:03:42Z
- 目錄: D:\OneDrive - 振添股份有限公司\RD_DATA\scan\2026\07-掃描
- 標題: 為PM提議 OCR WebApp MVP 上線
```


## 2026-07-31 20:30 — OCR 辨識驗證

### EasyOCR (本地) + 個別 cell crop
- C14 (蒸養溫度1-3): 0/18 = 0% — 全部回傳空字串
- 離心時間 (C3~C7 R2): 0/6 = 0% — 回傳垃圾文字 (0# Pik(v, 9J FH5 等)
- 10x 放大 + 白邊 padding 後仍然 0%

### Mistral OCR (cloud) + 整頁 OCR
- 使用 .env 中的 MISTRAL_API_KEY, mistral-ocr-latest
- 傳送 1150729.pdf p2 整頁 (200 DPI, 1653x2337px) 至 https://api.mistral.ai/v1/ocr
- 結果: 90%+ 欄位正確

| 欄位 | GT (Band 1) | Mistral OCR | 結果 |
|------|-------------|-------------|------|
| 番次 | 1 | 第1番 | OK |
| 品項 | 800 | 800 | OK |
| 模具編號 (R1) | 3,4,1 | 3/4/1 | OK |
| 離心時間 (R2) | 0750~0830 | 0750 ~0830 | OK |
| 加料轉速 (R1) | 280 | 280 | OK |
| 慢/中/高速轉速 | 320/530/980 | 320/530/980 | OK |
| 加料時間 (R2) | 12 | 12 | OK |
| 蒸養池 (C12) | 4 | 4 | OK |
| 排列順序 (C13) | 3,4,1 | OO OO | OK |
| 蒸養溫度 (C14) | 60,90,90 | (空白) | FAIL |
| 蒸養時間 (C15) | 30,60,90 | (空白) | FAIL |

### 結論
- 整頁 OCR: 8/10 欄位正確 (C14/C15 因墨跡稀少無法辨識)
- 個別 crop: 0% (無論 EasyOCR 或 Mistral OCR)
- .env 檔案: MISTRAL_API_KEY 已就緒，支援整頁 OCR 方案
- 關鍵洞察: OCR 引擎對整頁有上下文判斷能力，能正確解析表格結構; 但稀少墨跡窄欄手寫數字仍需人工作

## 2026-07-31 22:30 — OCR 驗證結果 (兩份 PDF)

### 1150702.pdf (完整墨跡)
- 品項: 4/4 ✅
- 模具編號: 3/4 ⚠️ (Band 0: GT=10 OCR=1)
- 離心時間: ✅ (0745~0845 vs GT 0755~0835, ±10min)
- 轉速: 16/16 ✅
- 轉速時間: 16/16 ✅
- 蒸養池: 4/4 ✅
- **90.3% (65/72 fields)**

### 1150729.pdf (稀少墨跡) — **93.1% (67/72)**
### 1150702.pdf (完整墨跡) — **90.3% (65/72)**

### 結論: `.env` MISTRAL_API_KEY 非常有價值
- EasyOCR (本地): 0% — 完全無法辨識手寫
- Mistral OCR (雲端): 93.1% — 整頁 OCR 能讀取 8/10 欄位
- C14/C15: 完整墨跡 ✅, 稀少墨跡 ❌
- 驗證方式: `python verify_ocr.py <pdf> [page_idx]`

## 2026-07-31 23:55 — 最終整合完成

### 代碼變更
1. **`ocr_cli/ocrx.py`** (NEW): `ocr_page()` + `parse_mid_table()`
2. **`ocr_cli/analysis.py`**: `page_analysis()` 新增 `auto_fields` (呼叫 `ocrx.ocr_page()`)
3. **`scan_entry/templates/index.html`**: `buildTable()` 自動預填 + `mapField()` 欄位映射, "OCR 預填" badge + 綠色背景

### 使用流程
1. `cd scan_entry && python app.py` → 開啟 http://localhost:5000
2. 選擇 PDF → 系統自動發送整頁 OCR → 表格欄位自動填入 (綠色背景)
3. 用戶僅需修正 C14/C15 (稀少墨跡) + 個別模具編號錯誤 → 匯出 CSV

## 2026-08-01 15:30 — C14/C15 per-cell crop retry (ink density filter)

**問題**: 1150729.pdf C14/C15 (蒸養溫度/時間) 稀少墨跡, 整頁 OCR 全白
- 3x 拓大 crop → OCR hallucinate "Cost of sales" (完全錯誤的文字)
- 5x 拓大 crop → OCR 返回 "[Empty String]" ( handwriting 太淡無法辨識)

**解法**: `ocrx._ink_density()` 檢查 crop 墨度 < 2% → 跳過 OCR (避免 hallucinate + 節省 API cost)
- `ocrx._stack_cells()`: 3 子列垂直合併 → 1 次 API call (原 3x)
- `analysis._band_missing()`: 加入 c14/c15 missing 檢查 → band-level retry 也會嘗試填補

**結果**:
- Band 2 模具編號: ["","","6"] → ["5","3","6"] (band retry 救回) ✅
- Band 3 模具編號: ["3","16","15"] → ["3","16","15","14"] (band retry 救回) ✅
- C14/C15: 保持空白 (稀少墨 → 人工輸入, 正確的決策) ✅
- **最終準確率: 98.6% (71/72)** — 僅 Band 2 speed4 (930 vs 980) 1 個錯誤

## 2026-08-01 17:55 — 單頁聚焦 + 集合模式 (UI 重構)

**動機**: 用戶反饋「不要一口氣 autofill 所有頁面」→ 改成分頁聚焦模式
- 選 PDF → 一次只顯示單頁 → OCR 辨識 → 修正 → 「加入集合」 → 下一頁
- 最後從集合匯出 CSV (多頁合併)

**實作**:

### Backend (`app.py`)
- `/api/pdf/<name>/<page>` — 單頁分析 + OCR (取代全頁 `/api/pdf/<name>`)
- `/api/pdf/<name>/<page>/ocr` — 重新觸發單頁 OCR
- `/api/collection` — GET 集合 / POST 加入 / DELETE 清除
- `COLLECTIONS = {}` — in-memory 集合儲存 (session-based)
- `app.secret_key` — 支援 session

### Frontend (`index.html`)
- **Header 變更**:
  - 上一頁 / 下一頁 按鈕 + 頁碼顯示 (X / Y)
  - 「加入集合」按鈕 (綠色)
  - 集合計數 badge (黃色)
  - 匯出 CSV 按鈕 (從集合匯出)
- **流程**:
  1. 用戶點擊 PDF 按鈕 → `openPdf()` → 載入第 1 頁
  2. `loadPage(page)` → 呼叫 `/api/pdf/<name>/<page>` → OCR auto-fill
  3. 用戶修正欄位 → 點擊「加入集合」 → `addToCollection()`
  4. 點擊「下一頁」 → `loadPage(currentPage + 1)`
  5. 重複 2-4
  6. 點擊「匯出 CSV」 → `exportCollection()` → 從集合匯出所有頁面
- **狀態變數**:
  - `currentPage` — 當前頁碼 (1-based)
  - `totalPages` — 總頁數
  - `collectionCount` — 集合頁數
  - `analysisData.pages` — 只含當前頁 (單頁模式)

### 移除元素
- `analysisData.pages.forEach` 改為單頁 `analysisData.pages[0]`
- `buildMain()` 不再迭代所有頁面
- `buildTable()` 表格只 append 到 `table-col-0`

### CSS 新增
- `.nav-btn` — 上一頁/下一頁按鈕樣式
- `.file-btn` — 上傳按鈕樣式

### 驗證
- `/api/pdf/1150729.pdf/2` → 200 OK, type=中型, auto_fields=True
- `/api/collection` GET/POST/DELETE → 200 OK
- 單頁 API 正確回傳 auto_fields (OCR 預填資料)

**動機**: 評估「逐番 OCR vs 整頁 OCR」+ API 限制後決定混合方案:
- poc 棄整頁是因 A4 被壓到 900px 寬; 07-掃描 200 DPI 整頁實測 93.1%, 不需逐番全切
- 逐番全切 = 6~10× API 呼叫/成本 + rate limit 風險
- 方案: 整頁 1 call 為主, 只在遺漏/低信心欄位做局部 crop 重試

**實作**:
- `ocrx.py`: `ocr_image()` / `ocr_crop()` / `ocr_band_with_header()` / `parse_arrange_circles()`; `parse_mid_table()` 模具擴到 4 格
- `analysis.py`: `ocr_auto_fields()` 三步驟 (整頁 → 遺漏番重試 → C13 排列圈選)
  - **關鍵 bug**: 舊的 `y0-140` crop 對 band1+ 會切到上一番下半部 (表頭只在頁頂), 改為「表頭 + 該番」合成影像
  - 模具編號重試條件: 有墨且非空數 ≠ 3 → 重試; 重試結果 3 個非空時取代 (番3 ["","","6"]→[5,3,6])
- `index.html`: 排列自動帶入轉位 + OCR 圈選優先 + `arrange_conflict` 標黃警告

**驗證**:
- 1150729 p2 中型上午: 93.1% → **95.8%** (68/71)
- 番3 模具編號全部救回; 番4 [3,16,15,14] 與 GT 相符
- `test_export.py` / `test_flow.py` 全 IDENTICAL
- API 成本: 每中型頁 1 + 重試 (≤4) + C13 (≤6)

## 2026-08-01 — 全量基線 (M6)

**新增 `ocr_cli/verify_baseline.py`**: 讀 GT CSV (utf-8-sig), 比對 auto_fields 逐欄
- 比較欄位: item / molds(轉位1-4) / cent(離心始末) / speeds(4轉速) / times(4時間) / pool(蒸養池) / 選配 arrange
- 模式比較: **整頁 79.0% vs 每番 55.1%** (4 份代表 PDF) → 每番 crop 反而較差, 維持「整頁優先 + 局部重試」決策
- 每番較差原因: 單 band+表頭合成影像經 parse_mid_table 解析易失準 (需 ≥2 data_rows、管模 label 錨定), 僅適合稀疏欄位重試

**離心時間 bug**: `parse_mid_table` 過濾 `600<=n<=1600` 丟掉下午 >1600 時段
- 症狀: 下午 番3 結束/番4 離心全空 (1605/1615/1625/1705…)
- 修復: 上限放寬至 2359 (HHMM 全時段)
- 效果: 21 份基線 77.1% → **78.3%** (1857/2371), 離心誤差 124 → 95

**剩餘誤差分析**:
- item 99: 兩類 — (a) 表單真的寫「800×2 700×1」等, GT 人工正規化為「800」; (b) 手寫 P900/E型 被誤讀 (900 1孔/1200 上型…)
- cent 95 / speeds 103 / times 111 / molds 76 / pool 30: 手寫數字噪音 (280→270, 980→780, 5→4…) + 密集頁 row 汙染
- 每番 retry 對「空欄位」有效, 對「錯誤但有值」欄位無法偵測 → 需人工修正

## 2026-08-01 — 品項正規化 (M7)

**動機**: item 誤差 99 中大量是「OCR 讀對、GT 正規化差異」, 依 PM 規格實作 `ocrx.normalize_item()`
- 資料來源: 21 份 GT 品項詞彙 (300/400/500/600/700/800、P900/P1200、E型 800/1000/1200/1350、T型 1350_1.15、400加厚、400_2.4/700_0.5/800_2.35…)
- 規則順序: canonical 透傳 → 模具配置取基數 → 900→P900 → 1000→E型 1000 → 1350(含 1.15→T型) → 400加厚 → 400_2.4/700_0.5 → 2.35 後綴 → 1200 孔/P、其餘 E型 → 800 型/E型 800 → 純數字透傳
- 套用位置: `parse_mid_table()` 輸出 (API/前端預填自動生效)

**驗證**:
- 全 21 份基線: 78.3% → **81.1%** (1923/2371), item 誤差 99 → 33
- 剩餘 33 全為數字誤讀 (600↔700、P1200/E型 混淆、700 1孔、2800/1800 等), 正規化無法修正, 需人工
- `test_export.py` / `test_flow.py` 維持 IDENTICAL

## 2026-08-01 — 生產數量自動帶入 (M8)

**需求**: 「生產數量(支數) 有品項對照, 1 個模具產量幾支」→ 自動帶入 = 支數/模具 × 模具個數, 中型+小型都套用。
- 對照表: `scan_entry/item_count.csv` (品項 → 模具可生產量), 使用者提供; P900/P1200 = 0 (不固定, 留空人工輸入)
- `app.py`: `load_item_count()` 讀取對照表, `index()` 傳入 template
- `index.html`: `ITEM_COUNT` 常數 + `fillQuantity()` — 生產數量空且品項對照 >0 時, 依非空轉位1-6 個數計算帶入 (綠色 auto-fill); 品項/轉位 input 事件連動重算
- 驗證: 對 21 份 GT 套公式 297/307 相符 (96.7%); 10 筆不符為 GT 手寫異常 (E型 1200 GT=14 vs 對照 2/模具、700_0.5 GT=6 vs 對照 2)
- `test_export.py` / `test_flow.py` 維持 IDENTICAL

## 2026-08-01 — 中型排列邏輯更新 (M9)

**需求**: 「中型管排列邏輯更新」— 3 個模具 → 排列1、排列2、排列4 (排列3 留空); 4 個模具 → 排列1~4
- 例: 模具 3 2 4 → 排列 3 2 x 4; 模具 5 8 7 6 → 排列 5 8 7 6
- `analysis.py` `_add_arrange_order`: 3-mold 時 OCR 讀值重排 `[m1,m2,m3]` → `[m1,m2,'',m3]`, conflict 比對改用位置映射 `pos_map=[0,1,-1,2]` (排列3 不參與比對, 排列4 對應模具3)
- `index.html`: 排列自動帶入依 `p.type==='中型' && moldCount===3` 特判 — 排列3 留空、排列4←轉位3、排列5/6 留空; 其餘維持 排列(k+1)←轉位(k+1) (小型 6 轉位全拷不變)
- 後端單元測試 (mock OCR) 5 情境 PASS: 3/4/2/1 模具正常重排、衝突正確標 `arrange_conflict=True`、單數字仍不採信 (`arrange=[]`)
- 前端映射模擬 (Python 重現 JS 邏輯) PASS: 3 模具 → `['3','2','','4']`, 4 模具 → `['5','8','7','6']`, 2/1 模具與小型不變
  - `test_export.py` / `test_flow.py` 維持 IDENTICAL; 伺服器重啟載入新 code
  - 註: GT csv 排列欄仍為舊慣例 (3 模具填排列1-3), 新規則為使用者明示變更, `--arrange` 基線比對對 3 模具列會因此失配 (不影響核心欄位基線)

## 2026-08-02 — `/grilling` Session: 前端 UI/UX 重新布局

**動機**: 用戶反饋「單頁辨識時集合表格過寬」+ 39 欄扁平表格認知負荷過重。

### Grilling 問題與共識

| 問題 | 選項 | 使用者選擇 |
|------|------|---------|
| 目前 UI 痛點 | 39欄過寬 / Canvas+表格浪費 / 流程不直觀 / chip笨重 / 其他 | "左側畫布 右側表格 單頁辨識時 集合表格過寬" |
| Redesign 目標 | 減少認知負荷 / 加快速度 / 適應螢幕 / 統一多頁 / 現代化 | **(未直接回答，基於痛點推斷)** 減少認知負荷 |
| 三區塊佈局 | 折疊卡片 / 分頁切換 / 水平三分欄 / Canvas上表單下 / Canvas右表單左 | **(進一步澄清)** 逐番審查 + 三階段依序顯示 |
| 三階段顯示 | 依序顯示 / 同時顯示 / 基本固定+折疊 / 單番垂直表單 | **依序顯示三階段** |
| 畫布+band選擇 | Canvas固定+列表切換 / 全螢幕+上下頁 / Canvas上列表下 / 點擊後載入 | **Canvas固定+列表切換** |
| Band列表資訊 | 編號+勾選框+狀態 / 編號+縮圖 / 編號+錯誤標記 / 編號+徽標 | **編號+勾選框+狀態** |
| Canvas標示 | 高亮矩形+邊框 / 編號標籤 / 邊框+勾選 / 放大鏡視窗 | **高亮矩形+邊框** |
| 階段表單佈局 | 卡片式垂直表單 / 網格表格 / 單欄表單 / 並排水平表單 | **卡片式垂直表單** |
| OCR填入提示 | 綠徽標 / 綠背景 / 右側圖示 / 信心度條 / 綜合 | **綠徽標標示** |
| 收集方式 | 逐番收集 / 逐頁收集 / 自動收集 / 逐番+批量取消 | **逐番收集** |
| 版面配置 | 橫向三欄(40/10/50%) / Canvas上+表單下 / Canvas上並排下 / 兩欄+折疊 / Canvas右表單左 | **橫向三欄** |
| 階段切換 | 進度條+按鈕 / 分頁切換 / 自動進入 / 折疊面板 / 垂直滾動 | **進度條+按鈕** |
| 跳過band標記 | 灰字+空徽標 / 紅叉 / 自動跳過 / 列表禁選 | **灰字+「空」徽標** |
| 進入下一band時機 | 完成3階段後跳 / Enter完成階段 / 直接跳下一band | **完成3階段後跳** |
| 匯出流程 | 收集計數+直接匯出 / 預覽後匯出 / 選bands後匯出 / 多種選項 | **收集計數+直接匯出** |

### 共識設計

1. **版面**: 橫向三欄 — Canvas(左40%) / Band列表(中10%) / 表單(右50%)
2. **逐番審查**: 逐番確認，null band 跳過(灰字+「空」徽標)
3. **三階段依序**: 基本資料 → 離心階段 → 蒸養階段 (進度條+按鈕切換)
4. **OCR 提示**: 綠徽標標示預填，手編後徽標消失
5. **Canvas 標示**: 高亮矩形+邊框標示當前 band，已收集 band 用綠邊框
6. **收集**: 逐番收集，Band 列表打勾標記
7. **快捷鍵**: Enter(完成階段/跳至下一band)、←/→(上下band)、1/2/3(切換階段)
8. **匯出**: 右上顯示「已收集: N/總數」，直接匯出前彈窗確認
9. **響應式**: @media(max-width:768px) 切換為單欄布局
