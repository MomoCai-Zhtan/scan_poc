# OCR WebApp MVP 開發計畫

> **協議來源**: OpenCode session `ses_0489d7cdfffeDaewfq4KXZcKsg` → Kilo 續接
> **工作目錄**: `D:\OneDrive - 振添股份有限公司\RD_DATA\scan\2026\07-掃描`
> **最後更新**: 2026-08-12 (新增 §9 欄位選擇器/後台管理; 詳細變更歷程見 process.md)

## 1. 專案概述

為離心製管廠**生產記錄表掃描輸入**建置 WebApp MVP。
- **前端**: Flask + Bootstrap + Vanilla JS
- **後端**: Python + OpenCV (版面分析) + EasyOCR (文字辨識)
- **輸出**: 39 欄結構化 CSV

### 表單類型
| 類型 | 特徵 | 每頁番數 | 每番行數 |
|------|------|---------|---------|
| **小型** | 小管配管記錄 | 10 番 | 3 子列 (180px/番) |
| **中型** | 中管配管記錄 | 6 番 | 2 子列 (264px/番) |

### CSV 39 欄 ( HEADER )
```
日期, 類型, 番數, 序, 品項, 時段, 生產數量(支數), 生產量修正(+/-量),
轉位1-6, 離心開始, 離心結束, 加料轉速, 慢速轉速, 中速轉速, 高速轉速,
加料時間, 慢速時間, 中速時間, 高速時間, 蒸養池, 入池時間,
蒸養溫度1-3, 蒸養階段1-3, 位置, 排列1-6
```

## 2. 中型表單欄位定義 (2026-07-31 確認)

基於 OpenCode session 最新對話確認的中型表單結構:

| 欄位 | 範圍 (x) | R1 | R2 | 備註 |
|------|---------|----|----|------|
| **C1** | 89-147 | 番/序 | — | 人工輸入 |
| **C2** | 147-252 | 品項 | — | 例: 800、400 加厚 (手寫中文) |
| **C3-C6** | 252-521 | 模具編號 | 離心時間 | R1=模具編號(3,4,1), R2=離心開始/結束(0750/0830) |
| **C7** | 521-587 | (空) | 離心時間延續 | R2 為離心結束續列 |
| **C8-C11** | 587-876 | 轉速 | 轉速時間 | R1=加料/慢速/中速/高速轉速, R2=對應時間 |
| **C12** | 876-958 | 蒸養池編號 | — | R1+R2 合併單欄 |
| **C13** | 958-1248 | 模具排列順序 | — | 切 4 格 |
| **C14** | 1248-1320 | 蒸養溫度1-3 | — | **3 子列** (1/2/3) |
| **C15** | 1320-1391 | 蒸養時間1-3 | — | **3 子列** (1/2/3) |
| **C16** | 1391-1564 | — | — | **忽略** (發現情形) |

> **重要更新**: C14 (蒸養溫度) 和 C15 (蒸養時間) 為**3 子列**結構, 而非 2 子列。
> **C3~C7 R2** = 離心時間 (開始 + 結束)
> **C12** = 蒸養池編號, R1+R2 合併

## 3. 當前狀態

### ✅ 已完成
- `app.py` — Flask webapp (上傳、分析、網格顯示、匯出 CSV)
- `analysis.py` — `page_analysis()`, `row_bands()`, `detect_arrange_grid()`, `find_lines_robust()`
- `structure.py` — PDF 渲染、線檢測、格子建構
- `check_v4.py` — 勾選框 (上/下午) 偵測與判定
- `index.html` — 三欄布局 + 逐番審查 (2026-08-02, 取代舊扁平表格 UI)
- `test_flow.py` / `test_export.py` — 流程驗證 (均 IDENTICAL)
- `verify_html.py` / `verify_js_braces.py` — 新增 UI 結構 + JS 配對驗證
- **版面分析驗證**: 全 21 個掃描 PDF 驗證 — 小型每頁 10 番、中型每頁 6 番、無未知型別
- **C12 切割**: `detect_arrange_grid` 已改回傳 4 方框, `/arrange/` 路由已實現
- **OCR auto-fill** (NEW): `ocrx.py` + `analysis.py` Mistral OCR 整頁辨識, `index.html` 自動預填
  - `.env` 中的 `MISTRAL_API_KEY` 支援 `mistral-ocr-latest` 整頁 OCR API
  - 1150729.pdf: **93.1%** (67/72 fields) — 轉速/時間/離心時間/蒸養池 100% 正確
  - EasyOCR (本地): 0% — 完全無法辨識手寫
- **EasyOCR 基準測試**: 1150729 中型 8 番 × 16 欄 = 128 格, 辨識率僅 6.2% → 維持人工輸入路線

### 🔄 進行中
- (已完成) C14/C15 3 子列切割 — 改用 OCR 整頁辨識, 無需單獨切割
- (已完成) C3~C7 R2 離心時間 — 通过 OCR 自動填入
- (已完成) C16 忽略 — OCR 跳過

### ✅ M1-M4 里程碑 (更新於 2026-07-31 23:55)
- M1: ✅ C14/C15 3 子列 — 改用 Mistral OCR 整頁辨識, `mid_band_layout()` 已實現
- M2: ✅ 離心時間 — `parse_mid_table()` 自動解析離心開始/結束時間
- M3: ✅ UI 更新 — `index.html` 顯示 "OCR 預填" 標示 + 綠色背景自動填入
- M4: ✅ CSV 驗證 — 93.1% 準確率 (67/72 fields correct)

### ✅ M5: 混合 OCR 策略 (更新於 2026-08-01)
**整頁 OCR 為主 + per-band 局部重試 + C13 排列圈選交叉驗證**
- `ocrx.py` 新增 `ocr_image()`(通用)、`ocr_crop()`(縮放+白邊)、`ocr_band_with_header()`(表頭+單番合成)、`parse_arrange_circles()`(C13 圈選數字)
- `parse_mid_table()` 模具編號擴充為 4 格 (中型 轉位1-4)
- `analysis.py` `ocr_auto_fields()` 重寫:
  1. 整頁 OCR (1 call) 為主
  2. `_retry_missing_bands()` — 遺漏欄位番次用「表頭+該番」合成 crop 重試 (模具編號非 3 個時也重試, 上限 4 番)
  3. `_add_arrange_order()` — C13 圈選 per-band crop (3x) 讀取排列順序, 與轉位交叉比對標 `arrange_conflict` (≥2 數才採信)
- `index.html`:
  - 排列1-6 加入 `mapField` (OCR 圈選值優先)
  - 無圈選值時自動帶入轉位 (PM 規則); 衝突時標黃 `.auto-warn` + tooltip 提示人工確認
- **驗證**: 1150729 p2 中型上午 準確率 93.1% (67/72) → **95.8% (68/71)**; 番3 模具編號 ["","","6"] → [5,3,6] 全部救回
- **API 成本**: 每中型頁 = 1 (整頁) + 遺漏番重試 (≤4) + 有模具番 C13 (≤6); 全對頁面僅需 1 call
- `test_export.py` / `test_flow.py` 維持 IDENTICAL

### ✅ M6: 全量基線 + 離心時間 filter bug 修復 (2026-08-01)
**新增 `ocr_cli/verify_baseline.py`**: 以 csv/115.07.*.csv 為 GT, 逐欄比對整頁/每番兩種模式, 輸出 debug/baseline_*.md
- 模式比較 (4 份代表 PDF): **整頁 79.0% > 每番 55.1%** → 維持整頁優先, 每番僅做局部重試
- **Bug**: `parse_mid_table` 離心時間過濾 `600<=n<=1600` 會丟掉下午 >1600 的時段 (1605/1615/1625/1705…) → 放寬至 `600<=n<=2359`
- 修復後全 21 份整頁基線: **77.1% → 78.3%** (1857/2371); 離心誤差 124 → 95
- 剩餘誤差分布: item 99 (多為 GT 正規化差異, eg. 表單寫「800×2 700×1」GT 記「800」、手寫 P900/E型 誤讀), cent 95, speeds 103, times 111, molds 76, pool 30 — 主要是手寫數字噪音

### ✅ M7: 品項正規化 (2026-08-01)
`ocrx.normalize_item()` 依 PM 規格 + 21 份 GT 詞彙實作, 套用於 `parse_mid_table` 輸出的 item:
- 模具配置 `800×2 700×1` → `800`; `900 *` → `P900` (GT 無純 900); `1200 …孔` → `P1200`, `1200 …型` → `E型 1200`
- `1000` → `E型 1000`; `1350` → `E型 1350`, `1350 1.15m` → `T型 1350_1.15`; `400 …四周/四角/加` → `400加厚`
- 後綴: `400 2.4` → `400_2.4`, `700 0.5` → `700_0.5`, `800 2*35` → `E型 800_2.35`, `1200 2X35` → `E型 1200_2.35`
- canonical (P/E/T型、加厚、純 300~800) 直接透傳
- 效果: 全 21 份基線 **78.3% → 81.1%** (1923/2371), item 誤差 99 → 33 (剩餘全為數字誤讀: 600↔700、P1200/E型 混淆、700 1孔等, 需人工)

### ✅ M8: 生產數量自動帶入 (2026-08-01)
**需求**: 「生產數量(支數) 有品項對照, 1 個模具產量幾支」→ 生產數量 = 支數/模具 × 模具個數, 中型+小型都套用
- 對照表 `scan_entry/item_count.csv` (使用者提供, 64 品項); P900/P1200 = 0 → 留空人工輸入
- `app.py` `load_item_count()` + `index.html` `fillQuantity()` 自動帶入 (綠色), 品項/轉位變動連動重算
- 驗證: 21 份 GT 公式套用 297/307 相符 (96.7%), 不符者為 GT 手寫異常 (E型 1200/700_0.5)

### ✅ M9: 中型排列邏輯更新 (2026-08-01)
**需求**: 中型 3 個模具 → 排列1、排列2、排列4 (排列3 留空); 4 個模具 → 排列1~4 依模具編號
- 例: 模具 3 2 4 → 排列 3 2 x 4; 模具 5 8 7 6 → 排列 5 8 7 6
- `ocr_cli/analysis.py` `_add_arrange_order`: 3-mold 時 OCR 讀值 `[m1,m2,m3]` 重排為 `[m1,m2,'',m3]`, conflict 比對位置映射 `pos_map=[0,1,-1,2]`
- `scan_entry/templates/index.html`: 排列自動帶入依 `p.type==='中型' && moldCount===3` 特判 — 排列3 留空、排列4←轉位3、排列5/6 留空; 其餘(含小型、4/2/1 模具)維持 排列(k+1)←轉位(k+1)
- 驗證: 後端單元 5 情境 PASS (3/4/2/1 模具、衝突標記、單數字不採信); 前端映射模擬 PASS; `test_export.py`/`test_flow.py` IDENTICAL; 伺服器已重啟 (新 PID)

### ✅ M10: 前端三欄布局 + 逐番審查 (2026-08-02, commit a27dfde)
**依 §8 共識 + re-layout-plan.md 實作**:
- `index.html` 全面重寫: 三欄 (Canvas 40% / 番次列表 12% / 階段表單 48%) + @media 768px 單欄
- 逐番審查: 點番次/畫布高亮藍色, 已收集綠框+打勾, 空番灰字+「空」徽標
- 三階段依序顯示: 基本資料(6欄) → 離心(16欄) → 蒸養(14欄), 進度條+上一步/下一步
- 快捷鍵: Enter(下一階段/收集) · 1/2/3(切階段) · ←/→(切番) · Esc(清除欄位)
- OCR 綠徽標 (手編後消失); 排列依轉位自動帶入 (中型3模具特判) + `arrange_conflict` 標黃; 生產數量公式帶入
- `app.py`: 新增 `POST /api/collection/band` (逐番收集, 每番=1列); 單頁 API 補 `date_iso/roc/disp` (原缺日期)
- 新增 `verify_html.py` + `verify_js_braces.py` (含 node --check 語法)
- 順帶修復: `loadPdfs()` 的 `PdfS` ReferenceError (原會中斷所有事件綁定)
- 驗證: verify 全 PASS; `test_flow.py`/`test_export.py` IDENTICAL; 冒煙 API OK

### ✅ M11: 結構 API 效能修復 (2026-08-02)
- **Bug**: `/api/pdf/<name>` (前端 openPdf 僅取頁數) 原 `analyze_pdf()` 對每一頁都跑 OCR → 21 頁逾時 (>30s)
- **修復**: `page_analysis(pdf, idx, ocr=True)` / `analyze_pdf(pdf, ocr=False)` 加參數; `/api/pdf/<name>` 改 `ocr=False` (結構免 OCR); 診斷工具/單頁 API 維持 OCR
- 實測: `analyze_pdf(ocr=False)` 整本 1.4s (vs 原 >30s); 單頁 `/api/pdf/<name>/<page>` 不受影響

## 4. 開發里程碑

### ✅ M12: 小型版面 OCR 管線 (2026-08-03)

**需求**: 小型版面 (1150702 p1, 每番 3 子列 180px, 6 轉位) 自動辨識 → 39 欄 CSV。
- 條帶 (10 番合併裁切) + 逐番 retry 的混合策略, `ocr_small_page()` 用 `_merge_fullest()` 逐欄合併兩者。

**實作**:
- `ocrx.py`: `parse_small_band`/`_parse_small_rows`(固定 23 欄 + anchor fallback)/`ocr_small_band`/`ocr_small_strip(raw=True)`/`parse_small_strip`/`_md_data_rows`/`_small_crop`/`_dig`/`_valid_range`/`_fullness`/`_merge_fullest`/`ocr_small_page`
  - 23 欄 markdown 固定布局: col0=番次 1=品項 2=管模 3-8=模具6 9-12=轉速 13=池(+入池) 21=溫度 22=階段; R2 col3=離心開始~結束、col9-12=時間; R3 col21/22=溫度3/階段3
  - `_valid_range`: 轉速 100~1400、時間 1~20、溫度/階段 1~150、入池 0600~2359 (清掉狹欄 crop 的離心/模具數字污染)
  - 逐欄 crop 預設關閉 (`field_crops=False`): 狹欄 (53-68px) 會幻覺 (工程表/財報/2017 日期)
- `analysis.py`: `SMALL_COLS` 加入; 小型分支 `result['auto_fields'] = ocrx.ocr_small_page(..., SMALL_COLS)`
- `verify_baseline.py`: `read_gt_small`/`compare_band_small` + pool_time/temps/stages 誤差分佈 regex
- `index.html`: `mapField` 補 `pool_time`/`temps`/`stages`(回退 c14/c15);「序」預設空值 + `collectBand` 移除自動遞增 (序 = 人工填寫)
- 新增 `小型版面規格.md` (版面結構 + OCR 規則 + 衍生規則文件)

**驗證** (1150702 p1, GT 8 個有值番, 312 欄位):
- 51.0% → `_merge_fullest` 合併後 **59.3% (185/312)**
- 誤讀 pollution 消除 (例: temps[0]=1440 → 誠實空白)
- 殘留錯誤皆結構性: 淡墨欄 (轉速/時間/溫度/階段) 掃描無墨 → 只能人工; cent/molds/item 數字誤讀 (17↔27、合併格 2446); 小型 crop 拼字 item 「�� ��」略過
- 已知限制: 淡墨欄任何 OCR 皆無法讀出, 僅能靠 GT 或人工; `_merge_fullest` 全張合併可能選到較完整但誤讀的 read (如 molds[4] 合併格)

### M1-M4: C14/C15 子列切割 + 離心時間 (已完成, 更新 2026-08-01)
- M1: ✅ C14/C15 3 子列 `mid_band_layout()` 實現 (c14_cells/c15_cells)
- M2: ✅ 離心時間 `parse_mid_table()` 自動解析 (centrifuge start/end)
- M3: ✅ UI `index.html` 顯示 C14/C15 crop preview + auto-fill
- M4: ✅ CSV mapping: 離心開始/結束 → CSV columns 14/15

### M5: 混合 OCR 策略 (2026-07-31)

## 5. 風險與對應

| 風險 | 對應措施 |
|------|---------|
| 子列 y 位置不穩定 | 使用 ink 分析動態偵測分隔線, 而非固定 offset |
| 手寫辨識率低 | EasyOCR 0% → 改用 Mistral OCR 整頁 (90%+) |
| C14/C15 稀少墨跡無法辨識 | 1150729 (稀少墨) → 手動; 1150702 (完整墨) → 自動 |
| C3~C7 R2 離心時間分配不明 | 對照 GT: 0745=開始, 0835=結束 |
| 中型每頁行數不固定 | `row_bands()` 已支援動態偵測 (6 番) |

## 6. OCR 辨識驗證結果 (更新於 2026-07-31 21:00)

### 方案 A: EasyOCR (本地) + 個別 cell crop
**0% 準確率**。EasyOCR 無法辨識手寫數字:
- C14: 0/18 = 0%
- 離心時間: 0/6 = 0%

### 方案 B: Mistral OCR (cloud) + 整頁 OCR
**98.6% 準確率** (71/72 fields correct, 1150729.pdf)

| 欄位 | GT | OCR | 結果 |
|------|-----|-----|------|
| 品項 | 800, 800, 700, 400加厚 | 800, 800, 700, 400加厚 | ✅ 100% (normalize_item) |
| 模具編號 | 3,4,1; 5,6,2; 5,3,6; 3,16,15,14 | 3,4,1; 5,6,2; 5,3,6; 3,16,15,14 | ✅ 100% (band retry) |
| 離心時間 | 0750~0830 | 0750~0830 | ✅ 100% |
| 轉速 | all 16 values | all 16 values | ✅ 100% |
| 轉速時間 | all 16 values | all 16 values | ✅ 100% |
| 蒸養池 | 4,2,3,1 | 4,2,3,1 | ✅ 100% |
| C14/C15 | 60/90/90, 30/60/90 | (empty) | ❌ (sparse ink, manual input)

| 欄位 | GT | OCR | 結果 |
|------|-----|-----|------|
| 品項 | 800, 800, 700, 400 | 800, 800, 700, 400 四周 | ✅ 100%* |
| 模具編號 | 3,4,1; 5,6,2; 5,3,6; 3,16,14 | 3,4,1; 5,6,2; -, -,6; 3,16, | ⚠️ (2 missed, sparse ink) |
| 離心時間 | 0750~0830 | 0750~0830 | ✅ 100% |
| 轉速 | all 16 values | all 16 values | ✅ 100% |
| 轉速時間 | all 16 values | all 16 values | ✅ 100% |
| 蒸養池 | 4,2,3,1 | 4,2,3,1 | ✅ 100% |

* 品項 "400加厚" 被辨識為 "400 四周" — 中文字意不同但數值正確

**關鍵發現**: C14/C15 蒸養溫度/時間在 1150702 (完整墨) 可辨識, 1150729 (稀少墨) 顯示空白

### 結論

**`.env` 非常有用** — `MISTRAL_API_KEY` 支援整頁 OCR，準確率 90%+

| 比較 | 方案 | 準確率 |
|------|------|--------|
| EasyOCR crop | 本地 | 0% |
| Mistral OCR (1150729.pdf) | 雲端 (`.env` key) | **93.1%** (67/72) |
| Mistral OCR (1150702 完整墨) | 雲端 | 90.3% (65/72) |

**策略**: 將 `ocrx.py` 整頁 OCR 結果自動填入表格，僅 C14/C15 與少量模具編號需人工修正。

## 7. 單頁聚焦 + 集合模式 (2026-08-01)

**動機**: 用戶反饋「不要一口氣 autofill 所有頁面」→ 改成分頁聚焦
- 選 PDF → 一次只顯示單頁 → OCR 辨識 → 修正 → 「加入集合」 → 下一頁
- 最後從集合匯出 CSV (多頁合併)

**API**:
- `GET /api/pdf/<name>/<page>` — 單頁分析 + OCR
- `POST /api/pdf/<name>/<page>/ocr` — 重新觸發單頁 OCR
- `GET /api/collection` — 取得集合
- `POST /api/collection` — 加入当前頁到集合
- `DELETE /api/collection` — 清除集合
- `POST /export` — 從集合匯出 CSV

**前端流程**:
1. 點擊 PDF 按鈕 → `openPdf()` → 載入第 1 頁 + OCR
2. `loadPage(page)` → 顯示單頁 + auto-fill 表格
3. 上一頁 / 下一頁 按鈕導航
4. 「加入集合」按鈕 → `addToCollection()` → 儲存当前頁表格資料
5. 「匯出 CSV」按鈕 → `exportCollection()` → 從集合匯出所有頁面

**驗證**:
  - ✅ 單頁 API 200 OK + auto_fields
  - ✅ Collection GET/POST/DELETE 200 OK
  - ✅ UI: 頁碼顯示 (X/Y)、上一頁/下一頁、加入集合按鈕

## 8. 前端 UI/UX 重新布局計畫 (2026-08-02 Grilling Session)

### 8.1 痛點
- 39 欄表格過寬，單頁辨識時集合表格過寬，認知負荷過重
- Canvas + 表格並排 Layout，桌面寬螢幕可用但窄螢幕擠滶

### 8.2 三欄 Layout (Horizontal Three-Column)
```
┌─────────────────────────────────────────────────────────────┐
│ Header (sticky): PDF選擇 | 頁碼 | 進度 | 匯出 | 收集計數    │
├──────┬─────┬───────────────────────────────────────────────┤
│      │     │ 三個階段依序顯示(預設階段1)                     │
│ Canvas│Band│                                               │
│ (40%) │列(│ Stage 1: 基本資料 (6欄)                         │
│      │10%)│   番號/序, 品項, 生產數量, 生產量修正, 位置, 時段│
│      │     │ Stage 2: 離心 (10欄)                            │
│      │     │   轉位1-6, 離心開始/結束, 4轉速, 4時間         │
│      │     │ Stage 3: 蒸養 (8欄)                             │
│      │     │   蒸養池, 入池時間, 3溫度, 3時間, 排列1-6      │
│      │     │                                               │
└──────┴─────┴───────────────────────────────────────────────┘
```

### 8.3 逐番審查流程 (Band-by-Band Review)
1. 選擇 PDF → 載入第 1 頁 → `GET /api/pdf/<name>/<page>`
2. Canvas 固定顯示影像，Band 列表顯示所有番次編號+勾選框
3. 點擊 Band → Canvas 高亮該 Band 區域 (藍色遮罩)
4. 右欄表單顯示三個階段，預設階段 1 (基本資料)
5. **進度條 + 上一步/下一步按鈕** 切換階段
6. 每個欄位: OCR 預填時顯示綠徽標，手動修改後徽標消失
7. 完成 3 階段 → 按「加入集合」(Enter 快捷鍵) → Band 列表打勾標記
8. 匯出: 右上角顯示「已收集: N/總數」，點匯出 → 彈窗確認 → `POST /export`

### 8.4 Canvas 與 Band 選擇
- **Canvas 固定顯示**，點擊 Band 區域或列表跳轉
- **高亮矩形 + 邊框**: 藍色半透明遮罩標示當前 Band，綠色邊框標示已收集
- **Band 列表**: 編號 + 勾選框 + 狀態 (灰字 +「空」徽標標示跳過)

### 8.5 鍵盤快捷鍵
| 按鍵 | 動作 |
|------|------|
| Enter | 完成當前階段 → 下一階段 (或跳到下一 Band) |
| ← / → | 上一/下一 Band |
| 1 / 2 / 3 | 切換到階段 1 / 2 / 3 |
| Escape | 重置當前欄位 |

### 8.6 響應式設計
```css
@media (max-width: 768px) {
  .layout-body { flex-direction: column; }
  .canvas-col { width: 100%; }
  .band-list { width: 100%; flex-direction: row; }
  .form-col { width: 100%; }
}
```

### 8.7 資料流程
```
1. 選擇 PDF → openPdf(name)
2. 載入第1頁 → GET /api/pdf/<name>/<page> → auto_fields
3. Canvas 顯示影像 + Band 列表
4. 點擊 Band → 顯示 Band 詳細資料(OCR 預填)
5. 進度條: Stage 1(基本) → Stage 2(離心) → Stage 3(蒸養)
6. 每步驟: OCR 預填(綠徽標) → 用戶修正(徽標消失)
7. 完成3 stages → 加入集合 (Enter)
8. Band 列表打勾標記
9. 下一 Band 或上一頁/下一頁導航
10. 匯出 CSV → POST /export
```

### 8.8 API 變更
- **現有 API 無需改動**: `/api/pdf/<name>/<page>` 返回單頁分析 + auto_fields
- **收集模式**: 逐番收集，使用者按「加入集合」後呼叫 `/api/collection` POST (band 資料)
- **匯出**: `/export` POST 接收來自集合的所有 rows

## 9. 欄位選擇器與後台管理 (2026-08-11~12, M35-M40 + 後續)

**動機**: 欄位切割原本全靠程式裡手刻座標常數, 表單改版就得改程式碼。改用「畫格子 → 點選/合併 → 命名 → 存成 JSON」的可視化工具, 讓非工程師也能重新框欄位。

### 9.1 工具演進
tkinter 拖曳畫框 (M35) → 自動偵測格線 + 點格子多選/合併 + Save/Load Session (M36) → 產出 template_regions 資料集 + 自動抓線/手動拉線輔助工具 (M37-M38) → 改寫成瀏覽器版 (HTML5 Canvas) 並加上 Admin Dashboard 做 Templates/Regions/Field Mappings 的 CRUD, 取代人工維護 JSON (M39-M40)。

### 9.2 格線偵測演算法 (2026-08-12 重寫)
小型/中型表單並非單純均勻網格, 而是「合併儲存格 (rowspan) + 只涵蓋部分欄寬的局部子分隔線」混合結構 (例如中型的「管模/時間」子列分隔線只在窄欄內出現; 「模具排列順序」欄用圓圈圖案完全沒有格線)。原本「整頁寬度覆蓋率 30% 門檻 + 笛卡兒積切網格」的作法必然漏判局部子線, 已改為: 疊合橫線/縱線遮罩後, 用輪廓巢狀關係取最內層 (無子輪廓) 的輪廓, 天然對應實際儲存格邊界, 無需為個別表單類型寫死規則。共用函式: `ocr_cli/detect_lib.py::detect_table_cells()`, web 版 (`scan_entry/app.py`) 與桌面版 (`ocr_cli/field_selector_cells.py`) 皆呼叫同一實作。

### 9.3 後台路由分離 + 登入
`/admin*`、`/selector`、`/api/selector/*` 從 `scan_entry/app.py` 移到獨立的 Flask Blueprint `scan_entry/admin_routes.py`(URL 不變), 並加上 session 登入保護 (未登入: 頁面導向 `/admin/login`, API 回 401)。帳密透過 `ADMIN_USERNAME`/`ADMIN_PASSWORD`(或 `_HASH`) 環境變數設定, 密碼以 werkzeug 雜湊儲存, 正式環境務必覆蓋預設密碼。

### 9.4 共用版面
新增 `scan_entry/templates/base.html`(header/container/footer blocks), 前台首頁與後台頁面 (`index.html`/`admin.html`/`field_selector.html`/`admin_login.html`) 皆改為繼承它, 各頁仍保留自己原本的視覺風格 (未強制統一 CSS)。

詳細每一步的修法/驗證記錄見 `process.md` 對應日期章節。
