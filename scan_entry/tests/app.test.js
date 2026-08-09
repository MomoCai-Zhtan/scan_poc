import { describe, it, expect, beforeEach } from 'vitest';

// --- Helpers extracted from app.js for unit testing ---
// These mirror the production logic in scan_entry/static/app.js

const STAGES = [
  {name:"基本資料", cols:["序","品項","生產數量(支數)","生產量修正(+/-量)","時段"]},
  {name:"離心", cols:["轉位1","轉位2","轉位3","轉位4","轉位5","轉位6",
                      "離心開始","離心結束","加料轉速","慢速轉速","中速轉速","高速轉速",
                      "加料時間","慢速時間","中速時間","高速時間"]},
  {name:"蒸養", cols:["蒸養池","入池時間","蒸養溫度1","蒸養溫度2","蒸養溫度3",
                      "蒸養階段1","蒸養階段2","蒸養階段3","位置",
                      "排列1","排列2","排列3","排列4","排列5","排列6"]},
];
const SELECT_COLS = ["時段"];
const ROW_GROUPS = [
  ["轉位1", "轉位2", "轉位3", "轉位4", "轉位5", "轉位6"],
  ["離心開始", "離心結束"],
  ["加料轉速", "慢速轉速", "中速轉速", "高速轉速"],
  ["加料時間", "慢速時間", "中速時間", "高速時間"],
  ["蒸養池", "入池時間"],
  ["蒸養溫度1", "蒸養溫度2", "蒸養溫度3"],
  ["蒸養階段1", "蒸養階段2", "蒸養階段3"],
];
const STAGE_SECTIONS = {
  1: [
    {name: "轉位",     color: "#0b5394", groups: [["轉位1", "轉位2", "轉位3", "轉位4", "轉位5", "轉位6"]]},
    {name: "離心時間", color: "#00897b", groups: [["離心開始", "離心結束"]]},
    {name: "轉速",     color: "#ef6c00", groups: [["加料轉速", "慢速轉速", "中速轉速", "高速轉速"]]},
    {name: "時間",     color: "#7b1fa2", groups: [["加料時間", "慢速時間", "中速時間", "高速時間"]]},
  ],
  2: [
    {name: "蒸養池",     color: "#2e7d32", groups: [["蒸養池", "入池時間"]]},
    {name: "蒸養溫度",   color: "#c62828", groups: [["蒸養溫度1", "蒸養溫度2", "蒸養溫度3"]]},
    {name: "蒸養階段",   color: "#6d4c41", groups: [["蒸養階段1", "蒸養階段2", "蒸養階段3"]]},
    {name: "位置與排列", color: "#455a64", groups: [["位置"], ["排列1", "排列2", "排列3", "排列4", "排列5", "排列6"]]},
  ],
};

function inheritedFieldToCol(field, idx){
  if (field === "item") return "品項";
  if (field === "pool_time") return "入池時間";
  if (field === "speeds") return ["", "慢速轉速", "中速轉速", "高速轉速"][idx];
  if (field === "temps") return "蒸養溫度" + (idx + 1);
  if (field === "stages") return "蒸養階段" + (idx + 1);
  return null;
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

function arrangeSource(k, pai, bandData, analysisData){
  let moldCount = 0;
  const d = bandData[k] || {vals: {}};
  for (let m = 1; m <= 6; m++){ if (d.vals["轉位" + m]) moldCount++; }
  if (analysisData.type === "中型" && moldCount === 3){
    if (pai === 1) return 0;
    if (pai === 2) return 1;
    if (pai === 3) return -1;
    if (pai === 4) return 2;
    return -1;
  }
  return pai - 1;
}

function recomputeDerived(k, bandData, analysisData, ITEM_COUNT){
  const d = bandData[k];
  if (!d) return;
  if (!d.autoCalc) d.autoCalc = {};
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
  const bf = null; // bandInfo not needed for arrange fallback test
  for (let p = 1; p <= 6; p++){
    const col = "排列" + p;
    if (d.vals[col]) continue;
    const ocrArr = bf && bf.arrange ? (bf.arrange[p - 1] || "") : "";
    if (ocrArr){ d.vals[col] = String(ocrArr); d.ocr[col] = true; }
    else {
      const src = arrangeSource(k, p, bandData, analysisData);
      if (src >= 0){
        const zv = d.vals["轉位" + (src + 1)] || "";
        if (zv) d.vals[col] = zv;
      }
    }
  }
}

function bandIsEmpty(k, analysisData, bandData){
  const af = analysisData && analysisData.auto_fields;
  if (!af) return false;
  const b = af[k];
  if (!b) return true;
  return !Object.keys(b).some(key => {
    const v = b[key];
    if (Array.isArray(v)) return v.some(x => x);
    return !!v;
  });
}

// --- Tests ---

describe('mapField', () => {
  it('maps 品項 from bf.item', () => {
    expect(mapField('品項', { item: '800' })).toBe('800');
  });
  it('returns undefined when bf is null', () => {
    expect(mapField('品項', null)).toBeUndefined();
  });
  it('maps 轉位1-6 from molds array', () => {
    const bf = { molds: ['A', 'B', 'C', 'D', 'E', 'F'] };
    expect(mapField('轉位3', bf)).toBe('C');
    expect(mapField('轉位6', bf)).toBe('F');
  });
  it('maps 離心開始/結束 from centrifuge tuple', () => {
    const bf = { centrifuge: ['0750', '0830'] };
    expect(mapField('離心開始', bf)).toBe('0750');
    expect(mapField('離心結束', bf)).toBe('0830');
  });
  it('maps 加料/慢速/中速/高速 轉速 from speeds array', () => {
    const bf = { speeds: ['280', '320', '530', '980'] };
    expect(mapField('加料轉速', bf)).toBe('280');
    expect(mapField('高速轉速', bf)).toBe('980');
  });
  it('maps 蒸養池 from steam_pool', () => {
    const bf = { steam_pool: 'A池' };
    expect(mapField('蒸養池', bf)).toBe('A池');
  });
  it('maps 入池時間 from pool_time', () => {
    const bf = { pool_time: '1513' };
    expect(mapField('入池時間', bf)).toBe('1513');
  });
  it('maps 蒸養溫度 from temps array (falls back to c14)', () => {
    const bf = { temps: ['60', '90', '90'] };
    expect(mapField('蒸養溫度2', bf)).toBe('90');
  });
  it('falls back to c14 when temps missing', () => {
    const bf = { c14: ['60', '90', '90'] };
    expect(mapField('蒸養溫度2', bf)).toBe('90');
  });
  it('maps 排列 from arrange array', () => {
    const bf = { arrange: ['1', '2', '3', '4', '5', '6'] };
    expect(mapField('排列4', bf)).toBe('4');
  });
  it('returns undefined for unknown col', () => {
    expect(mapField('unknown', {})).toBeUndefined();
  });
});

describe('inheritedFieldToCol', () => {
  it('maps item to 品項', () => {
    expect(inheritedFieldToCol('item', 0)).toBe('品項');
  });
  it('maps pool_time to 入池時間', () => {
    expect(inheritedFieldToCol('pool_time', 0)).toBe('入池時間');
  });
  it('maps speeds by index', () => {
    expect(inheritedFieldToCol('speeds', 1)).toBe('慢速轉速');
    expect(inheritedFieldToCol('speeds', 2)).toBe('中速轉速');
    expect(inheritedFieldToCol('speeds', 3)).toBe('高速轉速');
  });
  it('maps temps by index', () => {
    expect(inheritedFieldToCol('temps', 0)).toBe('蒸養溫度1');
    expect(inheritedFieldToCol('temps', 2)).toBe('蒸養溫度3');
  });
  it('maps stages by index', () => {
    expect(inheritedFieldToCol('stages', 0)).toBe('蒸養階段1');
    expect(inheritedFieldToCol('stages', 2)).toBe('蒸養階段3');
  });
  it('returns null for unknown field', () => {
    expect(inheritedFieldToCol('unknown', 0)).toBeNull();
  });
});

describe('arrangeSource', () => {
  const makeBandData = (molds) => ({
    0: { vals: { "轉位1": molds[0], "轉位2": molds[1], "轉位3": molds[2], "轉位4": molds[3], "轉位5": molds[4], "轉位6": molds[5] } }
  });

  it('中型 3 模具: 排列1←轉位1, 排列2←轉位2, 排列3留空, 排列4←轉位3', () => {
    const bd = makeBandData(['A', 'B', 'C', '', '', '']);
    const ad = { type: '中型' };
    expect(arrangeSource(0, 1, bd, ad)).toBe(0);
    expect(arrangeSource(0, 2, bd, ad)).toBe(1);
    expect(arrangeSource(0, 3, bd, ad)).toBe(-1);
    expect(arrangeSource(0, 4, bd, ad)).toBe(2);
    expect(arrangeSource(0, 5, bd, ad)).toBe(-1);
  });
  it('中型 3 模具: 排列5/6 留空', () => {
    const bd = makeBandData(['A', 'B', 'C', '', '', '']);
    const ad = { type: '中型' };
    expect(arrangeSource(0, 5, bd, ad)).toBe(-1);
    expect(arrangeSource(0, 6, bd, ad)).toBe(-1);
  });
  it('中型非 3 模具: 直接映射', () => {
    const bd = makeBandData(['A', 'B', '', '', '', '']);
    const ad = { type: '中型' };
    expect(arrangeSource(0, 1, bd, ad)).toBe(0);
    expect(arrangeSource(0, 2, bd, ad)).toBe(1);
    expect(arrangeSource(0, 3, bd, ad)).toBe(2);
  });
  it('小型: 直接映射 (pai-1)', () => {
    const bd = makeBandData(['A', 'B', '', '', '', '']);
    const ad = { type: '小型' };
    expect(arrangeSource(0, 1, bd, ad)).toBe(0);
    expect(arrangeSource(0, 6, bd, ad)).toBe(5);
  });
});

describe('recomputeDerived', () => {
  const ITEM_COUNT = { '800': 12, '700': 12 };

  it('auto-calculates 生產數量 from 品項 × 轉位數', () => {
    const bandData = {
      0: { vals: { "品項": "800", "轉位1": "A", "轉位2": "B", "轉位3": "C" }, autoCalc: {} }
    };
    const analysisData = { type: '中型', shift: '下午', rows: [] };
    recomputeDerived(0, bandData, analysisData, ITEM_COUNT);
    expect(bandData[0].vals["生產數量(支數)"]).toBe('36');
    expect(bandData[0].autoCalc["生產數量(支數)"]).toBe(true);
  });

  it('does not overwrite manual 生產數量', () => {
    const bandData = {
      0: { vals: { "品項": "800", "轉位1": "A", "生產數量(支數)": "99" }, autoCalc: { "生產數量(支數)": false } }
    };
    const analysisData = { type: '中型', shift: '下午', rows: [] };
    recomputeDerived(0, bandData, analysisData, ITEM_COUNT);
    expect(bandData[0].vals["生產數量(支數)"]).toBe('99');
  });

  it('fills 排列 from 轉位 when no OCR arrange', () => {
    const bandData = {
      0: { vals: { "轉位1": "A", "轉位2": "B", "轉位3": "C", "轉位4": "D", "轉位5": "E", "轉位6": "F" }, autoCalc: {}, ocr: {} }
    };
    const analysisData = { type: '小型', shift: '下午', rows: [] };
    recomputeDerived(0, bandData, analysisData, ITEM_COUNT);
    expect(bandData[0].vals["排列1"]).toBe('A');
    expect(bandData[0].vals["排列6"]).toBe('F');
  });
});

describe('bandIsEmpty', () => {
  it('returns true when auto_fields has no values', () => {
    const analysisData = { auto_fields: { 0: { item: '', molds: ['', '', '', ''], centrifuge: ['', ''], speeds: ['', '', '', ''], speed_times: ['', '', '', ''], steam_pool: '' } } };
    const bandData = {};
    expect(bandIsEmpty(0, analysisData, bandData)).toBe(true);
  });
  it('returns false when auto_fields has item', () => {
    const analysisData = { auto_fields: { 0: { item: '800', molds: ['', '', '', ''], centrifuge: ['', ''], speeds: ['', '', '', ''], speed_times: ['', '', '', ''], steam_pool: '' } } };
    const bandData = {};
    expect(bandIsEmpty(0, analysisData, bandData)).toBe(false);
  });
  it('returns false when no auto_fields (small form)', () => {
    const analysisData = { auto_fields: null };
    const bandData = {};
    expect(bandIsEmpty(0, analysisData, bandData)).toBe(false);
  });
});
