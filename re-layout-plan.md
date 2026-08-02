# 前端UI/UX重新布局實作計畫

> 基於 2026-08-02 Grilling Session 達成共識

## 1. 痛點與目標

**痛點**: 39 欄表格過寬，單頁辨識時集合表格過寬，認知負荷過重。

**目標**: 將 39 欄扁平表格重組為逐番審查模式，三個階段依序顯示，減少同時顯示的欄位數量。

## 2. 版面架構 (Consensus)

```
┌─────────────────────────────────────────────────────────────┐
│ Header (sticky): PDF選擇 | 頁碼導航 | 進度 | 匯出 | 收集計數 │
├─────────────────────────────────────────────────────────────┤
│  Canvas(40%) │ Band列表(10%) │ 表單(50%)                        │
│              │               │ 三階段依序: 基本→離心→蒸養      │
│  - 固定顯示   │ - 編號+勾選框  │ - 卡片式垂直表單                   │
│  - 高亮band   │ +空徽標       │ - 進度條+按鈕切換                 │
│  - 綠色邊框=   │ - 可點擊跳轸  │ - 綠徽標=OCR預填                 │
│    已收集    │               │                                  │
└─────────────────────────────────────────────────────────────┘
```

## 3. 三個審查階段欄位劃分

### 階段 1: 基本資料 (6 欄)
| 欄位 | 類型 |
|------|------|
| 番號/序 | 自動 |
| 品項 | OCR+手編 |
| 生產數量(支數) | OCR+公式計算 |
| 生產量修正(+/-量) | 手編 |
| 位置 | 手編 |
| 時段 | 自動(AM/PM下拉) |

### 階段 2: 離心階段 (10 欄)
| 欄位 | 類型 |
|------|------|
| 轉位1-6 | OCR+手編 |
| 離心開始 | OCR+手編 |
| 離心結束 | OCR+手編 |
| 加料轉速 | OCR |
| 慢速轉速 | OCR |
| 中速轉速 | OCR |
| 高速轉速 | OCR |
| 加料時間 | OCR |
| 慢速時間 | OCR |
| 中速時間 | OCR |
| 高速時間 | OCR |

### 階段 3: 蒸養階段 (8 欄)
| 欄位 | 類型 |
|------|------|
| 蒸養池 | OCR |
| 入池時間 | 手編 |
| 蒸養溫度1-3 | 手編(OCR稀少) |
| 蒸養階段1-3 | 手編(OCR稀少) |
| 排列1-6 | 公式(轉位對應) |

## 4. 資料流程

```
1. 選擇 PDF → openPdf(name)
2. 載入第1頁 → loadPage(1) → GET /api/pdf/<name>/<page>
3. Canvas 顯示影像 + band 列表顯示
4. 點擊 band → 顯示 band 詳細
5. 進度條: 階段1(基本) → 階段2(離心) → 階段3(蒸養)
6. 每個階段: OCR 預填(綠徽標) → 用戶修正(徽標消失)
7. 完成3階段 → 點「加入集合」(Enter快捷鍵)
8. Band列表打勾標記已收集
9. 匯出 CSV → POST /export
```

## 5. 後端 API 調整

### 現有 API (無需改動)
- `GET /api/pdf/<name>/<page>` — 返回單頁分析 + auto_fields
  ```json
  {
    "page": 2, "type": "中型", "rows": [[y0,y1], ...],
    "auto_fields": {0: {item, molds, speeds, ...}, 1: {...}, ...}
  }
  ```

### 新 API (用於逐番收集)
- `POST /api/collection/band` — 收集單個 band 資料
  ```json
  {pdf, page, band, type, date_iso, date_roc, date_disp, shift, fields: {...}}
  ```

## 6. 前端組件 (index.html)

### 6.1 主要函數改動
| 舊函數 | 新函數 | 說明 |
|--------|--------|------|
| buildMain() | buildLayout() | 三欄布局替換單頁表格 |
| buildTable() | buildStageForm(stage) | 依階段建立卡片式表單 |
| drawPage() | drawCanvas() | Canvas 上高亮 band 區域 |
| collectRows() | collectBand() | 收集當前 band 的3階段資料 |

### 6.2 新狀態變數
```js
let currentBand = null;       // 當前選中 band index
let currentStage = 0;         // 0=基本, 1=離心, 2=蒸養
let collectedBands = Set();   // 已收集的 band indices
let bandData = {};            // band index → 表單資料快取
```

### 6.3 鍵盤快捷鍵
| 按鍵 | 動作 |
|------|------|
| Enter | 完成當前階段 → 下一階段 (或跳到下一 band) |
| ← / → | 上一/下一 band |
| 1/2/3 | 切換到階段 1/2/3 |
| Escape | 重置當前欄位 |

### 6.4 響應式斷點
```css
@media (max-width: 768px) {
  .page-body { flex-direction: column; }
  .scan-col { width: 100%; }
  .band-list { width: 100%; display: flex; }
  .table-col { width: 100%; }
}
```

## 7. 測試驗證

### 7.1 保持向後兼容
- `test_flow.py` — 模擬 UI 輸出順序，比對 GT CSV
- `test_export.py` — 測試 /export API，比對匯出結果

### 7.2 UI 驗證腳本 (NEW)
- `verify_html.py` — 驗證 HTML 結構完整性 (3 欄布局, 進度條, band 列表)
- `verify_js_braces.py` — 驗證 JavaScript 大括號匹配

## 8. 實作步驟

1. **修改 index.html** — 重構為三欄布局 + 逐番審查流程
2. **修改 app.py** — 新增 /api/collection/band 路由
3. **添加驗證腳本** — verify_html.py + verify_js_braces.py
4. **測試** — 執行 test_flow.py + test_export.py 確認不破壞
5. **手動驗證** — 開啟 localhost:5000，確認流程完整

## 9. 風險

| 風險 | 對應措施 |
|------|---------|
| 三欄布局在窄螢幕擠滶 | @media 斷點切換為單欄 |
| OCR 徽標顯示邏輯錯誤 | mapField() 只在第一遍套用, 手編後不覆蓋 |
| Band 選擇狀態混亂 | collectedBands Set + Canvas 綠邊框同步 |
| Enter 快捷鍵干擾表單提交 | Enter僅在表單末尾按鈕觸發, 輸入框Enter不跳轉 |
