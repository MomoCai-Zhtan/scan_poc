// Cache buster: reload if server restarted
// TS provided by inline script
// cache buster handled by inline script


// PDFS provided by inline script
// HEADER provided by inline script
// ITEM_COUNT provided by inline script

// 審查階段欄位劃分 (逐番審查:三個階段依序顯示)
const STAGES = [
  {name:"基本資料", cols:["序","品項","生產數量(支數)","生產量修正(+/-量)","時段"]},
  {name:"離心", cols:["轉位1","轉位2","轉位3","轉位4","轉位5","轉位6",
                      "離心開始","離心結束","加料轉速","慢速轉速","中速轉速","高速轉速",
                      "加料時間","慢速時間","中速時間","高速時間"]},
  {name:"蒸養", cols:["蒸養池","入池時間","蒸養溫度1","蒸養溫度2","蒸養溫度3",
                      "蒸養階段1","蒸養階段2","蒸養階段3","位置","排列1","排列2","排列3","排列4","排列5","排列6"]},
];
const AUTO_COLS = ["日期", "類型", "番數"];   // 頁層級自動欄(不進階段表單)
const SELECT_COLS = ["時段"];
const ROW_GROUPS = [                         // 同一列顯示的欄位群組
  ["轉位1", "轉位2", "轉位3", "轉位4", "轉位5", "轉位6"],
  ["離心開始", "離心結束"],
  ["加料轉速", "慢速轉速", "中速轉速", "高速轉速"],
  ["加料時間", "慢速時間", "中速時間", "高速時間"],
  ["蒸養池", "入池時間"],
  ["蒸養溫度1", "蒸養溫度2", "蒸養溫度3"],
  ["蒸養階段1", "蒸養階段2", "蒸養階段3"],
];
const STAGE_SECTIONS = {                     // 階段 → 卡片區塊 section (彩色表頭 + 內容區)
  1: [                                        // 離心
    {name: "轉位",     color: "#0b5394", groups: [["轉位1", "轉位2", "轉位3", "轉位4", "轉位5", "轉位6"]]},
    {name: "離心時間", color: "#00897b", groups: [["離心開始", "離心結束"]]},
    {name: "轉速",     color: "#ef6c00", groups: [["加料轉速", "慢速轉速", "中速轉速", "高速轉速"]]},
    {name: "時間",     color: "#7b1fa2", groups: [["加料時間", "慢速時間", "中速時間", "高速時間"]]},
  ],
  2: [                                        // 蒸養
    {name: "蒸養池",     color: "#2e7d32", groups: [["蒸養池", "入池時間"]]},
    {name: "蒸養溫度",   color: "#c62828", groups: [["蒸養溫度1", "蒸養溫度2", "蒸養溫度3"]]},
    {name: "蒸養階段",   color: "#6d4c41", groups: [["蒸養階段1", "蒸養階段2", "蒸養階段3"]]},
    {name: "位置與排列", color: "#455a64", groups: [["位置"], ["排列1", "排列2", "排列3", "排列4", "排列5", "排列6"]]},
  ],
};

let pdfName = "";
let currentPage = 1;
let totalPages = 0;
let analysisData = null;      // 單頁分析 + auto_fields + 日期
let currentBand = null;       // 當前選中番次 index
let currentStage = 0;         // 0=基本 1=離心 2=蒸養
let bandData = {};            // bandIdx -> {vals:{col:val}, ocr:{col:true}, inherited:{col:true}}
let collectedBands = {};      // bandIdx -> 收集次數
let collectionCount = 0;      // 集合總列數 (server count)
let pageTotalBands = 0;
let showGrid = true;           // ToolBar: 顯示 C/R 格線覆疊
const pageImages = {};
let pageAborter = null;        // AbortController for in-flight page requests
let pdfStructure = null;       // 全頁結構 (from /api/pdf/<name>), for progressive rendering
let _debounceTimer = null;     // debounce timer for recomputeDerived/computePositions

function $(id){ return document.getElementById(id); }

function debounce(fn, ms){
  let t;
  return function(...args){
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), ms);
  };
}

function showMsg(text, ok){
  const m = $("msg");
  m.textContent = text;
  m.className = "msg " + (ok ? "ok" : "err");
  m.style.display = "";
}
function showLoading(text){
  const el = $("loading");
  if (el){
    el.querySelector("span").textContent = text || "處理中...";
    el.style.display = "flex";
  }
}
function hideLoading(){
  const el = $("loading");
  if (el) el.style.display = "none";
}
function showLayout(show){
  $("layoutBody").style.display = show ? "flex" : "none";
  $("emptyState").style.display = show ? "none" : "block";
}
function showPageNav(show){
  $("pageNav").style.display = show ? "inline" : "none";
}

function renderPageStructure(page){
  if (!pdfStructure || !pdfStructure.pages) return;
  const p = pdfStructure.pages[page - 1];
  if (!p) return;
  analysisData = {
    page: p.page || page,
    type: p.type || '',
    rows: p.rows || [],
    shift: p.shift || '',
    shift_conf: p.shift_conf || 0,
    h_lines: p.h_lines || [],
    v_lines: p.v_lines || [],
    size: p.size || [],
    date_iso: pdfStructure.date_iso || '',
    date_roc: pdfStructure.date_roc || '',
    date_disp: pdfStructure.date_disp || '',
    auto_fields: null,
  };
  currentBand = null;
  currentStage = 0;
  bandData = {};
  collectedBands = {};
  pageTotalBands = (analysisData.rows || []).length;
  $("pageInfo").textContent = page + " / " + totalPages;
  $("btnPrev").disabled = page <= 1;
  $("btnNext").disabled = page >= totalPages;
  $("dateInfo").textContent = "日期 " + (analysisData.date_disp || "");
  showLayout(true);
  buildBandList();
  buildStageForm();
  computePositions();
  updateCollInfo();
  loadCanvasImage();
}

function bandInfo(k){
  return analysisData && analysisData.auto_fields ? analysisData.auto_fields[k] : null;
}
function bandIsEmpty(k){
  const af = analysisData.auto_fields;
  if (!af) return false;              // 無 auto_fields(小型/OCR失敗)視為需審查
  const b = af[k];
  if (!b) return true;
  return !Object.keys(b).some(key => {
    const v = b[key];
    if (Array.isArray(v)) return v.some(x => x);
    return !!v;
  });
}
function getVal(k, col){
  const d = bandData[k];
  return d ? (d.vals[col] || "") : "";
}
function setVal(k, col, v, ocr){
  if (!bandData[k]) bandData[k] = {vals: {}, ocr: {}};
  bandData[k].vals[col] = v;
  if (ocr) bandData[k].ocr[col] = true;
  else delete bandData[k].ocr[col];
}

function mapField(csvCol, bf){
  if (!bf) return undefined;
  switch (csvCol) {
    case "品項": return bf.item || undefined;
    case "轉位1": return bf.molds[0] || undefined;
    case "轉位2": return bf.molds[1] || undefined;
    case "轉位3": return bf.molds[2] || undefined;
    case "轉位4": return bf.molds[3] || undefined;
    case "轉位5": return bf.molds[4] || undefined;
    case "轉位6": return bf.molds[5] || undefined;
    case "離心開始": return bf.centrifuge[0] || undefined;
    case "離心結束": return bf.centrifuge[1] || undefined;
    case "加料轉速": return bf.speeds[0] || undefined;
    case "慢速轉速": return bf.speeds[1] || undefined;
    case "中速轉速": return bf.speeds[2] || undefined;
    case "高速轉速": return bf.speeds[3] || undefined;
    case "加料時間": return bf.speed_times[0] || undefined;
    case "慢速時間": return bf.speed_times[1] || undefined;
    case "中速時間": return bf.speed_times[2] || undefined;
    case "高速時間": return bf.speed_times[3] || undefined;
    case "蒸養池": return bf.steam_pool || undefined;
    case "入池時間": return bf.pool_time || undefined;
    case "蒸養溫度1": return (bf.temps && bf.temps[0]) || (bf.c14 && bf.c14[0]);
    case "蒸養溫度2": return (bf.temps && bf.temps[1]) || (bf.c14 && bf.c14[1]);
    case "蒸養溫度3": return (bf.temps && bf.temps[2]) || (bf.c14 && bf.c14[2]);
    case "蒸養階段1": return (bf.stages && bf.stages[0]) || (bf.c15 && bf.c15[0]);
    case "蒸養階段2": return (bf.stages && bf.stages[1]) || (bf.c15 && bf.c15[1]);
    case "蒸養階段3": return (bf.stages && bf.stages[2]) || (bf.c15 && bf.c15[2]);
    case "排列1": return bf.arrange && bf.arrange[0];
    case "排列2": return bf.arrange && bf.arrange[1];
    case "排列3": return bf.arrange && bf.arrange[2];
    case "排列4": return bf.arrange && bf.arrange[3];
    case "排列5": return bf.arrange && bf.arrange[4];
    case "排列6": return bf.arrange && bf.arrange[5];
    default: return undefined;
  }
}

function inheritedFieldToCol(field, idx){
  // 後端 inherit_fields 的 (field, idx) → CSV 欄名
  if (field === "item") return "品項";
  if (field === "pool_time") return "入池時間";
  if (field === "speeds") return ["", "慢速轉速", "中速轉速", "高速轉速"][idx];
  if (field === "temps") return "蒸養溫度" + (idx + 1);
  if (field === "stages") return "蒸養階段" + (idx + 1);
  return null;
}

function initBand(k){
  if (bandData[k]) return;
  bandData[k] = {vals: {}, ocr: {}, inherited: {}, autoCalc: {}};
  const bf = bandInfo(k);
  if (bf){
    STAGES.forEach(s => s.cols.forEach(c => {
      const v = mapField(c, bf);
      if (v !== undefined && v !== null && v !== ""){
        bandData[k].vals[c] = String(v);
        bandData[k].ocr[c] = true;
      }
    }));
    // 繼承標示: 被繼承的欄位標記 (徽標顯示「繼承」)
    (bf.inherited || []).forEach(([field, idx]) => {
      const col = inheritedFieldToCol(field, idx);
      if (col && bandData[k].vals[col]){
        bandData[k].inherited[col] = true;
      }
    });
  }
  if (!bandData[k].vals["時段"]) bandData[k].vals["時段"] = analysisData.shift || "下午";
  recomputeDerived(k);
}

function arrangeSource(k, pai){
  let moldCount = 0;
  const d = bandData[k] || {vals: {}};
  for (let m = 1; m <= 6; m++){ if (d.vals["轉位" + m]) moldCount++; }
  if (analysisData.type === "中型" && moldCount === 3){
    if (pai === 1) return 0;   // 排列1 ← 轉位1
    if (pai === 2) return 1;   // 排列2 ← 轉位2
    if (pai === 3) return -1;  // 排列3 留空
    if (pai === 4) return 2;   // 排列4 ← 轉位3
    return -1;                 // 排列5/6 留空
  }
  return pai - 1;              // 排列(k+1) ← 轉位(k+1)
}

function recomputeDerived(k){
  const d = bandData[k];
  if (!d) return;
  if (!d.autoCalc) d.autoCalc = {};
  // 生產數量(支數) = 品項對照(支/模具) × 模具個數;空欄或仍是自動帶入值(未被人工手動修改過)才重算
  const qtyCol = "生產數量(支數)";
  const item = (d.vals["品項"] || "").trim();
  const per = ITEM_COUNT[item];
  if ((!d.vals[qtyCol] || d.autoCalc[qtyCol]) && per){
    let n = 0;
    for (let m = 1; m <= 6; m++){ if (d.vals["轉位" + m]) n++; }
    if (n > 0){
      d.vals[qtyCol] = String(per * n);
      d.autoCalc[qtyCol] = true;
    }
  }
  // 排列:OCR 圈選值優先,無則依轉位(中型3模具特判);僅空欄自動帶入
  const bf = bandInfo(k);
  for (let p = 1; p <= 6; p++){
    const col = "排列" + p;
    if (d.vals[col]) continue;
    const ocrArr = bf && bf.arrange ? (bf.arrange[p - 1] || "") : "";
    if (ocrArr){ d.vals[col] = String(ocrArr); d.ocr[col] = true; }
    else {
      const src = arrangeSource(k, p);
      if (src >= 0){
        const zv = d.vals["轉位" + (src + 1)] || "";
        if (zv) d.vals[col] = zv;
      }
    }
  }
}

function computePositions(){
  if (!analysisData || analysisData.type !== "小型") return;
  const n = (analysisData.rows || []).length;
  if (!n) return;
  const pools = [];
  for (let k = 0; k < n; k++){
    const d = bandData[k];
    const bf = bandInfo(k);
    pools.push((d && d.vals["蒸養池"]) || (bf && bf.steam_pool) || "");
  }
  const groups = {};
  pools.forEach((p, k) => { if (p) (groups[p] = groups[p] || []).push(k); });
  const POS = ["下", "中", "上"];
  Object.keys(groups).forEach(p => {
    groups[p].sort((a, b) => a - b).forEach((k, i) => {
      if (i >= POS.length) return;
      if (!bandData[k]) initBand(k);
      if (!bandData[k].vals["位置"]) setVal(k, "位置", POS[i], false);
    });
  });
}

function syncFieldDom(col){
  const inp = $("fld-" + col);
  if (inp && bandData[currentBand]){
    inp.value = bandData[currentBand].vals[col] || "";
  }
}

function buildStageForm(){
  const wrap = $("stageForm");
  wrap.innerHTML = "";
  if (currentBand === null){
    wrap.innerHTML = '<div class="hint">請點擊左側番次 (或畫布) 開始逐番審查</div>';
    updateProgress();
    return;
  }
  if (!bandData[currentBand]) {
    initBand(currentBand);
  }
  recomputeDerived(currentBand);
  const stage = STAGES[currentStage];
  const card = document.createElement("div");
  card.className = "stage-card";

  const head = document.createElement("div");
  head.className = "stage-head";
  const title = document.createElement("h4");
  title.textContent = "番 " + (currentBand + 1) + " · 階段 " + (currentStage + 1) + ": " + stage.name;
  head.appendChild(title);
  if (collectedBands[currentBand]){
    const tag = document.createElement("span");
    tag.className = "collected-tag";
    tag.textContent = "已收集";
    head.appendChild(tag);
  }
  card.appendChild(head);

  if (currentStage === 0){
    const info = document.createElement("div");
    info.className = "auto-info";
    info.textContent = "日期 " + (analysisData.date_disp || "") +
                       " · 類型 " + (analysisData.type || "") +
                       " · 番數 " + (currentBand + 1);
    card.appendChild(info);
  }

  const makeInput = (col, d) => {
    let inp;
    if (SELECT_COLS.includes(col)){
      inp = document.createElement("select");
      ["上午", "下午"].forEach(s => {
        const o = document.createElement("option");
        o.value = s; o.textContent = s;
        inp.appendChild(o);
      });
      inp.value = d.vals[col] || analysisData.shift || "下午";
    } else {
      inp = document.createElement("input");
      inp.type = "text";
      inp.value = d.vals[col] || "";
    }
    inp.id = "fld-" + col;
    inp.dataset.col = col;
    const handleEdit = () => {
      setVal(currentBand, col, inp.value, false);
      if (col === "生產數量(支數)"){
        const d2 = bandData[currentBand];
        if (d2.autoCalc) d2.autoCalc[col] = false;   // 人工手動改過,之後品項/轉位變動不再覆蓋
      }
      if (col === "品項" || col.startsWith("轉位")){
        clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(() => {
          recomputeDerived(currentBand);
          syncFieldDom("生產數量(支數)");
          if (currentStage === 2) buildStageForm();
        }, 100);
      }
      if (col === "蒸養池"){
        clearTimeout(_debounceTimer);
        _debounceTimer = setTimeout(() => {
          computePositions();
          syncFieldDom("位置");
        }, 100);
      }
      const badge = inp.parentNode.querySelector(".ocr-badge");
      if (badge) badge.remove();
      inp.classList.remove("has-ocr");
    };
    inp.oninput = handleEdit;
    if (SELECT_COLS.includes(col)) inp.onchange = handleEdit;
    return inp;
  };

  const markOcr = (el, col, inp) => {
    const d = bandData[currentBand];
    if (d.ocr[col] && d.vals[col]){
      inp.classList.add("has-ocr");
      const badge = document.createElement("span");
      badge.className = "ocr-badge";
      badge.textContent = "OCR";
      el.appendChild(badge);
    }
    // 繼承標示: 從上一番複製的欄位 (橙色徽標, 提示人工確認)
    if (d.inherited && d.inherited[col] && d.vals[col]){
      const badge = document.createElement("span");
      badge.className = "inherit-badge";
      badge.textContent = "繼承";
      badge.title = "從上一番自動帶入,請確認";
      el.appendChild(badge);
    }
    const bf = bandInfo(currentBand);
    if (bf && bf.arrange_conflict && col.startsWith("排列")){
      inp.classList.add("auto-warn");
      inp.title = "OCR 排列順序與轉位不符,請人工確認";
    }
    if (bf && bf.item_uncertain && bf.item_uncertain.length && col === "品項"){
      inp.classList.add("auto-warn");
      const msgs = [];
      if (bf.item_uncertain.includes("vocab")) msgs.push("不在已知品項詞彙表內");
      if (bf.item_uncertain.includes("neighbor")) msgs.push("與前後番品項不同");
      inp.title = "品項可疑 (" + msgs.join("、") + "),請人工確認是否誤讀 (例如讀到鄰欄數字)";
    }
  };

  const buildCell = (col) => {
    const cell = document.createElement("div");
    cell.className = "field-cell";
    const lbl = document.createElement("label");
    lbl.textContent = col;
    lbl.htmlFor = "fld-" + col;
    cell.appendChild(lbl);
    const inp = makeInput(col, bandData[currentBand]);
    cell.appendChild(inp);
    markOcr(cell, col, inp);
    return cell;
  };

  const groups = [];
  const flat = stage.cols;
  for (let i = 0; i < flat.length;){
    const g = ROW_GROUPS.find(x => flat[i] === x[0] && x.every((c, k) => flat[i + k] === c));
    if (g){ groups.push(g); i += g.length; }
    else { groups.push([flat[i]]); i++; }
  }

  const sections = STAGE_SECTIONS[currentStage];
  if (sections){
    sections.forEach(sec => {
      const secEl = document.createElement("div");
      secEl.className = "form-section";
      const head = document.createElement("div");
      head.className = "section-head";
      head.style.background = sec.color || "#0b5394";
      head.textContent = sec.name;
      secEl.appendChild(head);
      const body = document.createElement("div");
      body.className = "section-body";
      sec.groups.forEach(g => {
        const row = document.createElement("div");
        row.className = g.length > 1 ? "field-row grid-row" : "field-row";
        g.forEach(col => row.appendChild(buildCell(col)));
        body.appendChild(row);
      });
      secEl.appendChild(body);
      card.appendChild(secEl);
    });
  } else {
    groups.forEach(g => {
      const d = bandData[currentBand];
      const row = document.createElement("div");
      row.className = "field-row";
      if (g.length > 1){
        row.classList.add("grid-row");
        g.forEach(col => row.appendChild(buildCell(col)));
      } else {
        const col = g[0];
        const lbl = document.createElement("label");
        lbl.textContent = col;
        lbl.htmlFor = "fld-" + col;
        row.appendChild(lbl);
        const inp = makeInput(col, d);
        row.appendChild(inp);
        markOcr(row, col, inp);
      }
      card.appendChild(row);
    });
  }
  wrap.appendChild(card);
  updateProgress();
}

function updateProgress(){
  const fill = $("progressFill");
  const lbl = $("stageLabel");
  fill.style.width = ((currentStage + 1) / STAGES.length * 100) + "%";
  lbl.textContent = "階段 " + (currentStage + 1) + "/" + STAGES.length + " (" + STAGES[currentStage].name + ")";
  $("btnStagePrev").disabled = currentStage === 0;
  $("btnStageNext").disabled = currentStage >= STAGES.length - 1;
}

function nextStage(){
  if (currentBand === null) return;
  if (currentStage < STAGES.length - 1){ currentStage++; buildStageForm(); }
  else collectBand();
}
function prevStage(){
  if (currentStage > 0){ currentStage--; buildStageForm(); }
}

function buildBandList(){
  const list = $("bandList");
  list.innerHTML = "";
  if (!analysisData || !analysisData.rows) return;
  analysisData.rows.forEach((r, k) => {
    const item = document.createElement("div");
    item.className = "band-item";
    const collected = !!collectedBands[k];
    const ck = document.createElement("span");
    ck.className = "ck";
    ck.textContent = collected ? "✓" : "";
    if (collected) item.classList.add("collected");
    if (k === currentBand) item.classList.add("on");
    item.appendChild(ck);
    const num = document.createElement("span");
    num.className = "num";
    num.textContent = (k + 1) + "番";
    item.appendChild(num);
    if (bandIsEmpty(k)){
      item.classList.add("empty");
      const b = document.createElement("span");
      b.className = "band-empty-badge";
      b.textContent = "空";
      item.appendChild(b);
    }
    item.onclick = () => selectBand(k);
    list.appendChild(item);
  });
}

function drawCanvas(){
  const canvas = $("scanCanvas");
  const img = pageImages[currentPage];
  if (!analysisData || !img) return;
  if (canvas.width !== img.width){ canvas.width = img.width; canvas.height = img.height; }
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  (analysisData.rows || []).forEach((b, k) => {
    const y = b[0], h = b[1] - b[0];
    const isCur = k === currentBand;
    const isCol = (collectedBands[k] || 0) > 0;
    if (isCur){
      ctx.fillStyle = "rgba(66,133,244,.25)";
      ctx.strokeStyle = "#4285f4";
    } else if (isCol){
      ctx.fillStyle = "rgba(52,168,83,.14)";
      ctx.strokeStyle = "#34a853";
    } else {
      ctx.fillStyle = "rgba(0,0,0,.05)";
      ctx.strokeStyle = "#ccc";
    }
    ctx.fillRect(0, y, canvas.width, h);
    ctx.lineWidth = isCur ? 3 : 1.2;
    ctx.strokeRect(0, y, canvas.width, h);
    ctx.fillStyle = isCur ? "#4285f4" : (isCol ? "#34a853" : "#888");
    ctx.font = "bold 13px sans-serif";
    ctx.fillText((k + 1) + "番", 8, y + 18);
  });
  if (showGrid){
    const scale = canvas.clientWidth / canvas.width;
    const fs = Math.max(11, Math.round(38 * scale));
    ctx.font = "bold " + fs + "px sans-serif";
    ctx.lineWidth = Math.max(1, Math.round(2 * scale));
    ctx.strokeStyle = "rgba(214,48,49,.55)";
    ctx.fillStyle = "#d63031";
    (analysisData.v_lines || []).forEach((x, i) => {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
      ctx.fillText("C" + (i + 1), x + 4, fs + 4);
    });
    (analysisData.h_lines || []).forEach((y, i) => {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
      ctx.fillText("R" + (i + 1), 4, y + fs);
    });
  }
}

function alignCanvasToBand(k){
  const scroller = document.querySelector(".canvas-col");
  const canvas = $("scanCanvas");
  const img = pageImages[currentPage];
  if (!scroller || !canvas || !img || !analysisData) return;
  const r = (analysisData.rows || [])[k];
  if (!r || canvas.height === 0) return;
  const dispH = canvas.getBoundingClientRect().height;
  if (dispH <= scroller.clientHeight) return;          // 整張畫布都看得見 → 不需捲動
  const sy = dispH / canvas.height;
  const y0 = r[0] * sy, y1 = r[1] * sy;
  if (y0 >= scroller.scrollTop && y1 <= scroller.scrollTop + scroller.clientHeight) return; // 已完全可見
  const target = y0 - (scroller.clientHeight - (y1 - y0)) / 2;
  scroller.scrollTo({ top: Math.max(0, target), behavior: "smooth" });
}

function selectBand(k){
  if (k < 0 || !analysisData || k >= (analysisData.rows || []).length) return;
  currentBand = k;
  currentStage = 0;
  initBand(k);
  buildBandList();
  drawCanvas();
  buildStageForm();
  updateAddBandButton();
  alignCanvasToBand(k);
}

function updateAddBandButton(){
  const btn = $("btnAddBand");
  const collected = currentBand !== null && !!collectedBands[currentBand];
  btn.textContent = collected ? "更新集合 (Enter)" : "加入集合 (Enter)";
}

function syncBandListAndCanvas(){
  buildBandList();
  drawCanvas();
}

function updateCollInfo(){
  const el = $("collInfo");
  el.textContent = "已收集: " + collectionCount;
  el.style.display = collectionCount > 0 ? "inline-block" : "none";
  const ps = $("pageStatus");
  if (ps){
    const done = Object.values(collectedBands).reduce((a, b) => a + b, 0);
    ps.textContent = "本頁已收集: " + done + " / " + pageTotalBands +
                     (analysisData ? "  (頁 " + currentPage + "/" + totalPages + ")" : "");
  }
}

async function collectBand(){
  if (currentBand === null){ showMsg("請先選擇番次", false); return; }
  initBand(currentBand);
  recomputeDerived(currentBand);
  const d = bandData[currentBand];
  const row = {};
  AUTO_COLS.forEach(c => {
    if (c === "日期") row[c] = analysisData.date_iso || "";
    else if (c === "類型") row[c] = analysisData.type || "";
    else if (c === "番數") row[c] = String(currentBand + 1);
  });
  STAGES.forEach(s => s.cols.forEach(c => row[c] = d.vals[c] || ""));
  const body = {
    pdf: pdfName,
    page: currentPage,
    band: currentBand,
    date_iso: analysisData.date_iso || "",
    date_roc: analysisData.date_roc || "",
    date_disp: analysisData.date_disp || "",
    type: analysisData.type || "",
    shift: d.vals["時段"] || analysisData.shift || "",
    fields: row
  };
  showLoading(collectedBands[currentBand] ? "更新集合..." : "加入集合...");
  try {
    const res = await fetch("/api/collection/band", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    });
    const out = await res.json();
    if (out.ok){
      collectedBands[currentBand] = 1;
      collectionCount = out.count;
      bandData[currentBand].vals["序"] = "";   // 序號由用戶自行填寫
      updateCollInfo();
      syncBandListAndCanvas();
      updateAddBandButton();
      const verb = out.updated ? "已更新" : "已收集";
      showMsg(verb + "番" + (currentBand + 1) + " (集合共 " + collectionCount + " 列)", true);
      const next = (analysisData.rows || []).findIndex((_, idx) => idx > currentBand && !(collectedBands[idx] || 0));
      if (next >= 0) selectBand(next);
    } else {
      showMsg("加入失敗: " + (out.error || "?"), false);
    }
  } catch (e) {
    showMsg("加入失敗", false);
  } finally {
    hideLoading();
  }
}

async function exportCollection(){
  showLoading("從集合匯出 CSV...");
  try {
    const res = await fetch("/api/collection");
    const coll = await res.json();
    if (!coll.items.length){ showMsg("集合為空,請先加入番次", false); return; }
    const allRows = [];
    let date_iso = '', date_roc = '';
    coll.items.forEach(it => {
      date_iso = it.date_iso || date_iso;
      date_roc = it.date_roc || date_roc;
      if (it.kind === "band") allRows.push(it.fields || {});
      else (it.rows || []).forEach(r => allRows.push(r));
    });
    if (!confirm("確定匯出 " + allRows.length + " 列至 " + (date_roc || "?") + " 的 CSV?")){
      return;
    }
    const body = {pdf: pdfName, date_iso: date_iso, date_roc: date_roc, rows: allRows};
    const expRes = await fetch("/export", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    });
    const out = await expRes.json();
    if (out.ok){
      showMsg("已匯出 " + out.path + " (" + out.rows + " 列)", true);
    } else {
      showMsg("匯出失敗: " + (out.error || "?"), false);
    }
  } catch (e) {
    showMsg("匯出失敗", false);
  } finally {
    hideLoading();
  }
}

function resetBand(){
  if (currentBand === null) return;
  delete bandData[currentBand];
  initBand(currentBand);
  computePositions();
  buildStageForm();
  showMsg("番" + (currentBand + 1) + " 已重置為 OCR 預填值", true);
}

async function reOcrBand(){
  if (currentBand === null || !pdfName) return;
  showLoading("重新辨識第 " + (currentBand + 1) + " 番...");
  try {
    const res = await fetch("/api/pdf/" + encodeURIComponent(pdfName) + "/" + currentPage +
                            "/band/" + currentBand + "/ocr", {method: "POST"});
    const out = await res.json();
    if (out.ok && out.fields){
      if (analysisData.auto_fields){
        analysisData.auto_fields[currentBand] = out.fields;
      }
      delete bandData[currentBand];
      initBand(currentBand);
      recomputeDerived(currentBand);
      buildStageForm();
      updateCollInfo();
      showMsg("番" + (currentBand + 1) + " 重新辨識完成", true);
    } else {
      showMsg("重新辨識失敗: " + (out.error || "無結果"), false);
    }
  } catch (e) {
    showMsg("重新辨識失敗: " + e.message, false);
  } finally {
    hideLoading();
  }
}

async function syncCollectedBands(){
  // 從伺服器集合同步「此頁已收集」狀態,避免離開頁面再回來時勾選狀態遺失
  try {
    const res = await fetch("/api/collection");
    const coll = await res.json();
    (coll.items || []).forEach(it => {
      if (it.kind === "band" && it.pdf === pdfName && it.page === currentPage){
        collectedBands[it.band] = 1;
      }
    });
    collectionCount = coll.count || 0;
  } catch (e) { /* 同步失敗不阻擋頁面載入 */ }
}

async function loadPage(page){
  if (pageAborter) pageAborter.abort();
  pageAborter = new AbortController();
  const signal = pageAborter.signal;
  currentPage = page;

  renderPageStructure(page);

  showLoading("OCR 辨識第 " + page + " 頁...");
  try {
    const res = await fetch("/api/pdf/" + encodeURIComponent(pdfName) + "/" + page, {signal});
    if (!res.ok){ showMsg("無法載入第 " + page + " 頁", false); return; }
    const data = await res.json();
    if (data.auto_fields){
      analysisData.auto_fields = data.auto_fields;
    }
    bandData = {};
    collectedBands = {};
    await syncCollectedBands();
    buildBandList();
    buildStageForm();
    computePositions();
    updateCollInfo();
    drawCanvas();
    showMsg("第 " + page + " 頁 OCR 辨識完成 (" + pageTotalBands + " 番)", true);
  } catch (e) {
    if (e.name === 'AbortError') return;
    showMsg("載入失敗: " + e.message, false);
  } finally {
    hideLoading();
  }
}

function loadCanvasImage(){
  const img = new Image();
  pageImages[currentPage] = img;
  img.onload = () => {
    const canvas = $("scanCanvas");
    canvas.width = img.width;
    canvas.height = img.height;
    drawCanvas();
    if (currentBand === null){
      let first = (analysisData.rows || []).findIndex((_, k) => !bandIsEmpty(k));
      if (first < 0) first = 0;
      selectBand(first);
    }
  };
  img.src = "/img/" + encodeURIComponent(pdfName) + "/" + currentPage;
}

async function openPdf(name){
  pdfName = name;
  currentPage = 1;
  totalPages = 0;
  collectionCount = 0;
  updateCollInfo();
  showPageNav(false);
  showLayout(false);
  showLoading("分析 PDF 結構...");
  try {
    const res = await fetch("/api/pdf/" + encodeURIComponent(name));
    if (!res.ok){ showMsg("無法分析 " + name, false); return; }
    pdfStructure = await res.json();
    totalPages = pdfStructure.pages.length;
    showPageNav(true);
    $("dateInfo").textContent = "日期 " + (pdfStructure.date_disp || "");

    // Fetch expected accuracy
    try {
      const accRes = await fetch("/api/accuracy/" + encodeURIComponent(name));
      const accData = await accRes.json();
      if (accData.accuracy != null) {
        const badge = document.createElement("span");
        badge.className = "badge";
        badge.style.marginLeft = "8px";
        badge.textContent = "預期準確率: " + accData.accuracy + "%";
        badge.title = "基於歷史 GT 資料的 OCR 辨識準確率";
        $("dateInfo").appendChild(badge);
      }
    } catch (e) { /* ignore accuracy fetch error */ }

    renderPageStructure(currentPage);
    showMsg("載入結構完成 (共 " + totalPages + " 頁)，OCR 背景辨識中...", true);
    hideLoading();
    loadPage(currentPage);
  } catch (e) {
    showMsg("載入失敗: " + e.message, false);
  } finally {
    hideLoading();
  }
}

function loadPdfs(){
  const group = $("pdfGroup");
  group.innerHTML = "";
  PDFS.forEach(p => {
    const btn = document.createElement("button");
    btn.className = "pdf-btn";
    btn.textContent = p;
    btn.onclick = () => {
      group.querySelectorAll(".pdf-btn").forEach(b => b.classList.remove("on"));
      btn.classList.add("on");
      openPdf(p);
    };
    group.appendChild(btn);
  });
  if (PDFS.length){
    group.children[0].classList.add("on");
    openPdf(PDFS[0]);
  }
  $("pdfUpload").onchange = (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    showLoading("上傳中...");
    fetch("/upload", {method: "POST", body: form})
      .then(r => r.json())
      .then(data => {
        if (data.ok){ showMsg("上傳成功: " + data.name, true); location.reload(); }
        else showMsg("上傳失敗: " + (data.error || "?"), false);
      })
      .catch(() => showMsg("上傳失敗", false))
      .finally(hideLoading);
  };
  $("btnPrev").onclick = () => { if (currentPage > 1) loadPage(currentPage - 1); };
  $("btnNext").onclick = () => { if (currentPage < totalPages) loadPage(currentPage + 1); };
  $("btnExport").onclick = exportCollection;
  $("btnAddBand").onclick = collectBand;
  $("btnResetBand").onclick = resetBand;
  $("btnReOcrBand").onclick = reOcrBand;
  $("btnStagePrev").onclick = prevStage;
  $("btnStageNext").onclick = nextStage;
  $("gridToggle").onchange = (ev) => { showGrid = ev.target.checked; drawCanvas(); };
  $("btnReOcr").onclick = async () => {
    if (!pdfName || !currentPage) return;
    showLoading("重新 OCR 第 " + currentPage + " 頁...");
    try {
      await fetch("/api/pdf/" + encodeURIComponent(pdfName) + "/" + currentPage + "/ocr",
                  {method: "POST"});
      await loadPage(currentPage);
      showMsg("第 " + currentPage + " 頁 OCR 已更新", true);
    } catch (e) {
      showMsg("重新 OCR 失敗: " + e.message, false);
    } finally {
      hideLoading();
    }
  };
  const toolbar = document.querySelector(".canvas-toolbar");
  const dragHandle = toolbar.querySelector(".toolbar-drag");
  let dragState = null;
  dragHandle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    const wrap = toolbar.parentElement;
    const wrapRect = wrap.getBoundingClientRect();
    const barRect = toolbar.getBoundingClientRect();
    dragState = { dx: e.clientX - barRect.left, dy: e.clientY - barRect.top, wrapRect, w: barRect.width, h: barRect.height };
    dragHandle.setPointerCapture(e.pointerId);
  });
  dragHandle.addEventListener("pointermove", (e) => {
    if (!dragState) return;
    const { dx, dy, wrapRect, w, h } = dragState;
    const left = Math.max(4, Math.min(e.clientX - wrapRect.left - dx, wrapRect.width - w - 4));
    const top = Math.max(4, Math.min(e.clientY - wrapRect.top - dy, wrapRect.height - h - 4));
    toolbar.style.left = left + "px";
    toolbar.style.top = top + "px";
    toolbar.style.right = "auto";
  });
  const endDrag = () => { dragState = null; };
  dragHandle.addEventListener("pointerup", endDrag);
  dragHandle.addEventListener("pointercancel", endDrag);
  $("scanCanvas").onclick = (ev) => {
    if (!analysisData || !pageImages[currentPage]) return;
    const rect = ev.currentTarget.getBoundingClientRect();
    const img = pageImages[currentPage];
    const y = (ev.clientY - rect.top) * (img.height / rect.height);
    let hit = -1;
    (analysisData.rows || []).forEach((b, k) => {
      if (y >= b[0] && y < b[1]) hit = k;
    });
    if (hit >= 0) selectBand(hit);
  };
}

document.addEventListener("keydown", (e) => {
  const t = e.target;
  const inField = t && (t.tagName === "INPUT" || t.tagName === "SELECT");
  const inButton = t && t.tagName === "BUTTON";
  if (e.key === "Enter"){
    if (inButton || currentBand === null) return;
    e.preventDefault();
    if (currentStage < STAGES.length - 1) nextStage(); else collectBand();
    return;
  }
  if (e.key === "Escape" && inField){
    e.preventDefault();
    t.value = "";
    setVal(currentBand, t.dataset.col, "", false);
    t.classList.remove("has-ocr");
    const badge = t.parentNode.querySelector(".ocr-badge");
    if (badge) badge.remove();
    return;
  }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight"){
    if (inField) return;
    e.preventDefault();
    const n = analysisData ? (analysisData.rows || []).length : 0;
    if (!n || currentBand === null) return;
    let nb = currentBand + (e.key === "ArrowRight" ? 1 : -1);
    if (nb < 0) nb = n - 1;
    if (nb >= n) nb = 0;
    selectBand(nb);
    return;
  }
  if (/^[123]$/.test(e.key) && !inField && currentBand !== null){
    const s = parseInt(e.key, 10) - 1;
    if (s >= 0 && s < STAGES.length){ currentStage = s; buildStageForm(); }
  }
});

loadPdfs();
