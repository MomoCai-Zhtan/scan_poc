# -*- coding: utf-8 -*-
"""inherit_fields 單元測試: 慢/中/高速轉速、蒸養溫度1~3、蒸養階段1~3、品項、入池時間繼承。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocrx

def run():
    # 情境: 番0 完整, 番1 缺慢/中/高速+時間+溫度+階段+品項+入池, 番2 全空(無模具)
    bands = {
        0: {'item': '800', 'molds': ['3', '4', '1'],
            'speeds': ['280', '320', '530', '980'], 'speed_times': ['10', '20', '30', '40'],
            'temps': ['60', '90', '90'], 'stages': ['30', '60', '90'],
            'steam_pool': '4', 'pool_time': '0840'},
        1: {'item': '', 'molds': ['5', '6', '2'],
            'speeds': ['280', '', '', ''], 'speed_times': ['10', '', '', ''],
            'temps': ['', '', ''], 'stages': ['', '', ''],
            'steam_pool': '2', 'pool_time': ''},
        2: {'item': '', 'molds': ['', '', ''],
            'speeds': ['', '', '', ''], 'speed_times': ['', '', '', ''],
            'temps': ['', '', ''], 'stages': ['', '', ''],
            'steam_pool': '2', 'pool_time': ''},
    }
    r = ocrx.inherit_fields(bands)

    ok = True
    # 番1: 加料/慢/中/高速全繼承; 加料時間有值, 慢/中/高速時間繼承
    b1 = r[1]
    assert b1['speeds'] == ['280', '320', '530', '980'], b1['speeds']
    assert b1['speed_times'] == ['10', '20', '30', '40'], b1['speed_times']
    assert b1['temps'] == ['60', '90', '90'], b1['temps']
    assert b1['stages'] == ['30', '60', '90'], b1['stages']
    # 品項繼承 (品項空 + 模具非空)
    assert b1['item'] == '800', b1['item']
    # 入池時間同池回填 (番1 池=2, 但番0 池=4 無 2 的入池 → 不繼承)
    assert b1['pool_time'] == '', b1['pool_time']
    # 繼承標示: speeds[0] 本來有值不標記, 其餘 3 個空白被填入; speed_times 空白被填入
    inh = b1.get('inherited', [])
    assert ('speeds', 1) in inh and ('speeds', 2) in inh and ('speeds', 3) in inh, inh
    assert ('speed_times', 1) in inh and ('speed_times', 2) in inh and ('speed_times', 3) in inh, inh
    assert ('temps', 0) in inh and ('temps', 1) in inh and ('temps', 2) in inh, inh
    assert ('stages', 0) in inh and ('stages', 1) in inh and ('stages', 2) in inh, inh
    assert ('item', 0) in inh, inh

    # 番2: 模具全空 → 品項不繼承; speeds/speed_times 全空 → 全繼承
    b2 = r[2]
    assert b2['item'] == '', b2['item']   # 模具空 → 不繼承品項
    assert b2['speeds'] == ['280', '320', '530', '980'], b2['speeds']
    assert b2['speed_times'] == ['10', '20', '30', '40'], b2['speed_times']
    assert b2['temps'] == ['60', '90', '90'], b2['temps']
    assert b2['stages'] == ['30', '60', '90'], b2['stages']
    assert b2['pool_time'] == '', b2['pool_time']

    # 情境2: 同池入池時間回填 — 番0 池=2 入池=1513, 番1 池=2 入池空 → 回填
    bands2 = {
        0: {'item': '400', 'molds': ['1', '2', '3'],
            'speeds': ['280', '350', '500', '900'], 'temps': ['60', '80', '80'],
            'stages': ['30', '60', '90'], 'steam_pool': '2', 'pool_time': '1513'},
        1: {'item': '400', 'molds': ['4', '5', '6'],
            'speeds': ['280', '350', '500', '900'], 'temps': ['60', '80', '80'],
            'stages': ['30', '60', '90'], 'steam_pool': '2', 'pool_time': ''},
    }
    r2 = ocrx.inherit_fields(bands2)
    assert r2[1]['pool_time'] == '1513', r2[1]['pool_time']
    assert ('pool_time', 0) in r2[1].get('inherited', []), r2[1].get('inherited')

    # 情境2b: 奇數番(1-indexed)=0-indexed偶數 入池空, 參照下一偶數番同池入池
    # 番0 (0-indexed even) pool=2 pool_time='', 番1 (0-indexed odd) pool=2 pool_time='1513'
    # → 番0 應從番1 回填入池時間
    bands2b = {
        0: {'item': '400', 'molds': ['1', '2', '3'],
            'speeds': ['280', '350', '500', '900'], 'temps': ['60', '80', '80'],
            'stages': ['30', '60', '90'], 'steam_pool': '2', 'pool_time': ''},
        1: {'item': '400', 'molds': ['4', '5', '6'],
            'speeds': ['280', '350', '500', '900'], 'temps': ['60', '80', '80'],
            'stages': ['30', '60', '90'], 'steam_pool': '2', 'pool_time': '1513'},
    }
    r2b = ocrx.inherit_fields(bands2b)
    assert r2b[0]['pool_time'] == '1513', r2b[0]['pool_time']
    assert ('pool_time', 0) in r2b[0].get('inherited', []), r2b[0].get('inherited')

    # 情境3: 連鎖繼承不擴散 — 番0 品項誤讀, 番1 品項空(繼承番0), 番2 品項空
    # 番2 應繼承「真實讀到的 C2」= 番0 的誤讀值 (因番1 是繼承值, 不當來源)
    # 但若番0 誤讀, 番2 不應再擴散 — 驗證 prev['item'] 只記錄真實 C2
    bands3 = {
        0: {'item': '800', 'molds': ['3', '4', '1'],
            'speeds': ['280', '320', '530', '980'], 'temps': ['60', '90', '90'],
            'stages': ['30', '60', '90'], 'steam_pool': '4', 'pool_time': '0840'},
        1: {'item': '', 'molds': ['5', '6', '2'],
            'speeds': ['280', '', '', ''], 'temps': ['', '', ''],
            'stages': ['', '', ''], 'steam_pool': '2', 'pool_time': ''},
        2: {'item': '', 'molds': ['7', '8', '9'],
            'speeds': ['280', '', '', ''], 'temps': ['', '', ''],
            'stages': ['', '', ''], 'steam_pool': '2', 'pool_time': ''},
    }
    r3 = ocrx.inherit_fields(bands3)
    # 番1 繼承番0 的 800
    assert r3[1]['item'] == '800', r3[1]['item']
    # 番2 也繼承 800 (來源 = 番0 真實 C2, 非番1 繼承值)
    assert r3[2]['item'] == '800', r3[2]['item']
    # 番2 的 inherited 標示 item
    assert ('item', 0) in r3[2].get('inherited', []), r3[2].get('inherited')

    # 情境4: 番0 品項誤讀, 番1 品項空繼承, 番2 品項「真實讀到」不同值
    # 番2 不繼承 (已有真實值), 且番2 成為新的 prev['item'] 來源
    bands4 = {
        0: {'item': '800', 'molds': ['3', '4', '1'],
            'speeds': ['280', '320', '530', '980'], 'temps': ['60', '90', '90'],
            'stages': ['30', '60', '90'], 'steam_pool': '4', 'pool_time': '0840'},
        1: {'item': '', 'molds': ['5', '6', '2'],
            'speeds': ['280', '', '', ''], 'temps': ['', '', ''],
            'stages': ['', '', ''], 'steam_pool': '2', 'pool_time': ''},
        2: {'item': '700', 'molds': ['7', '8', '9'],
            'speeds': ['280', '', '', ''], 'temps': ['', '', ''],
            'stages': ['', '', ''], 'steam_pool': '2', 'pool_time': ''},
        3: {'item': '', 'molds': ['10', '11', '12'],
            'speeds': ['280', '', '', ''], 'temps': ['', '', ''],
            'stages': ['', '', ''], 'steam_pool': '2', 'pool_time': ''},
    }
    r4 = ocrx.inherit_fields(bands4)
    assert r4[1]['item'] == '800', r4[1]['item']   # 番1 繼承番0
    assert r4[2]['item'] == '700', r4[2]['item']   # 番2 真實值, 不繼承
    assert r4[3]['item'] == '700', r4[3]['item']   # 番3 繼承番2 真實值 (非番0)
    assert ('item', 0) in r4[3].get('inherited', []), r4[3].get('inherited')

    print('ALL PASS ✅')
    print('番1 speeds:', b1['speeds'])
    print('番1 temps:', b1['temps'])
    print('番1 stages:', b1['stages'])
    print('番1 item:', b1['item'])
    print('番1 inherited:', b1['inherited'])
    print('番2 item (模具空不繼承):', b2['item'])
    print('情境2 番1 pool_time (同池回填):', r2[1]['pool_time'])
    print('情境3 番2 item (連鎖繼承來源=番0 真實C2):', r3[2]['item'])
    print('情境4 番3 item (繼承番2 真實值, 非番0):', r4[3]['item'])

    # 情境5: OCR normalize — 4W → 400, VV → 00, S → 5
    assert ocrx._normalize_ocr_text('4W') == '400'
    assert ocrx._normalize_ocr_text('VV') == '00'
    assert ocrx._normalize_ocr_text('S00') == '500'
    assert ocrx._normalize_ocr_text('B8') == '88'
    assert ocrx._normalize_ocr_text('G6') == '66'
    assert ocrx._normalize_ocr_text('正常123') == '正常123'  # 非純數字不處理
    print('OCR normalize: 4W->400, VV->00, S00->500, B8->88, G6->66')

if __name__ == '__main__':
    run()