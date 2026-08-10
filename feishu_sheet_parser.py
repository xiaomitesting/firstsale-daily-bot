#!/usr/bin/env python3
"""
飛書首銷表 → 飛書卡片 JSON
用法：被 bot 調用，輸出 JSON 到 stdout
"""

import json, sys, re
from datetime import datetime

def parse_num(s):
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    s = str(s).replace(",", "").replace("%", "").strip()
    if not s or s in ("—", "-", "N/A", "/"): return None
    try: return float(s)
    except: return None

def parse_date(d):
    s = str(d).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[4:6]}/{s[6:8]}"
    return s

def build_card_from_feishu(sheet_data, product_name=""):
    """從飛書 API 返回的 cells 數據生成卡片"""
    rows = sheet_data.get("rows", [])
    if not rows:
        return None
    
    # === Row 1: 表頭 ===
    r1 = rows[0] if len(rows) > 0 else []
    # === Row 2: 數值 ===
    r2 = rows[1] if len(rows) > 1 else []
    # === Row 3: 日均目標 ===
    r3 = rows[2] if len(rows) > 2 else []
    # === Row 4: 日均達成率 ===
    r4 = rows[3] if len(rows) > 3 else []
    # === Row 5: 上代實際 ===
    r5 = rows[4] if len(rows) > 4 else []
    
    # 從表頭取產品名
    if not product_name and r1:
        name_cell = r1[0] if r1 else ""
        if isinstance(name_cell, dict):
            name_cell = name_cell.get("value", "")
        if name_cell:
            product_name = str(name_cell).split("\n")[0].strip()
    
    # === 核心指標 (Row 2, Col E-K) ===
    def cell_val(row, idx):
        if idx >= len(row): return None
        c = row[idx]
        if isinstance(c, dict): c = c.get("value", "")
        return c
    
    summary = {
        "target": parse_num(cell_val(r2, 4)),      # E: 渠道首销目标
        "achieved": parse_num(cell_val(r2, 5)),     # F: 首销合计达成
        "rate": cell_val(r2, 6),                     # G: 整体达成率
        "time_progress": cell_val(r2, 7),            # H: 时间进度
        "progress_gap": cell_val(r2, 8),             # I: 进度落差
        "prev_gen": parse_num(cell_val(r2, 9)),      # J: 上代达成
        "yoy": cell_val(r2, 10),                     # K: 同比变幅
    }
    
    # === 每日 SO (Row 2, Col L-AJ) ===
    dates = []
    values = []
    prev_values = []
    daily_targets = []
    
    for i in range(11, 36):  # L=11 到 AJ=35
        date_val = cell_val(r1, i)
        so_val = parse_num(cell_val(r2, i))
        target_val = parse_num(cell_val(r3, i))
        prev_val = parse_num(cell_val(r5, i))
        
        if date_val:
            d = parse_date(date_val)
            if d and (so_val or target_val or prev_val):
                dates.append(d)
                values.append(so_val or 0)
                daily_targets.append(target_val or 0)
                prev_values.append(prev_val or 0)
    
    # === 渠道數據 (讀取更多行) ===
    channels = []
    for row in rows[5:]:  # 從第6行開始找渠道
        if not row or len(row) < 6:
            continue
        
        # 找渠道名（在 C 或 D 列）
        ch_name = None
        for ci in [2, 3]:
            c = cell_val(row, ci)
            if c and isinstance(c, str) and c.strip() and c.strip() not in ("合计", "日均目标", "日均达成率", "上代实际"):
                ch_name = c.strip()
                break
        
        if not ch_name:
            continue
        
        # 跳過 D列為「合计」的行（米家合计等）
        d_val = cell_val(row, 3)
        if d_val and isinstance(d_val, str) and d_val.strip() == "合计":
            continue
        
        # 找目標和達成（E 和 F 列）
        target = parse_num(cell_val(row, 4))
        achieved = parse_num(cell_val(row, 5))
        
        # 如果是「合计」行或總計行，跳過
        if ch_name in ("合计", "LEEDS", product_name, "全渠道合计"):
            continue
        
        if target or achieved:
            channels.append({"name": ch_name, "target": target, "achieved": achieved})
    
    # === 組裝卡片 ===
    components = []
    
    # KPI 指標卡
    kpi = []
    if summary["target"] is not None:
        kpi.append({"title": "首銷目標", "value": f"{int(summary['target']):,}"})
    if summary["achieved"] is not None:
        kpi.append({"title": "已達成", "value": f"{int(summary['achieved']):,}"})
    rate = summary["rate"]
    if rate:
        r = str(rate).replace("%", "").strip()
        try: kpi.append({"title": "達成率", "value": f"{float(r):.1f}%"})
        except: kpi.append({"title": "達成率", "value": str(rate)})
    gap = summary["progress_gap"]
    if gap:
        g = str(gap).replace("pp", "").replace("%", "").strip()
        try: kpi.append({"title": "進度落差", "value": f"{float(g)}pp"})
        except: kpi.append({"title": "進度落差", "value": str(gap)})
    if summary["prev_gen"] is not None:
        kpi.append({"title": "上代同期", "value": f"{int(summary['prev_gen']):,}"})
    yoy = summary["yoy"]
    if yoy:
        y = str(yoy).replace("%", "").strip()
        try: kpi.append({"title": "同比", "value": f"{float(y):.1f}%"})
        except: kpi.append({"title": "同比", "value": str(yoy)})
    
    if kpi:
        components.append({"type": "kpi_group", "items": kpi})
    
    # 每日SO趨勢
    if dates and values:
        chart = []
        for i, d in enumerate(dates):
            if values[i] > 0:
                chart.append({"date": d, "value": values[i], "series": product_name})
        for i, d in enumerate(dates):
            if i < len(prev_values) and prev_values[i] > 0:
                chart.append({"date": d, "value": prev_values[i], "series": "上代"})
        
        if chart:
            components.append({"type": "text", "content": "**📈 每日SO趨勢**", "text_size": "heading-4"})
            components.append({
                "type": "line", "x": "date", "y": "value", "series": "series",
                "data": chart, "height": "280px"
            })
    
    # 渠道側
    if channels:
        components.append({"type": "text", "content": "**📊 渠道側**", "text_size": "heading-4"})
        
        total_t = sum(c["target"] or 0 for c in channels)
        total_a = sum(c["achieved"] or 0 for c in channels)
        
        rows_data = []
        for ch in channels:
            t = ch["target"]
            a = ch["achieved"]
            rate = (a / t * 100) if t and a else None
            rows_data.append({
                "渠道": ch["name"],
                "目標": f"{int(t):,}" if t else "—",
                "已達成": f"{int(a):,}" if a else "—",
                "達成率": f"{rate:.1f}%" if rate else "—",
            })
        
        total_rate = (total_a / total_t * 100) if total_t else None
        rows_data.append({
            "渠道": "📊 合計",
            "目標": f"{int(total_t):,}" if total_t else "—",
            "已達成": f"{int(total_a):,}" if total_a else "—",
            "達成率": f"{total_rate:.1f}%" if total_rate else "—",
        })
        
        components.append({
            "type": "table",
            "columns": [
                {"key": "渠道", "name": "渠道"},
                {"key": "目標", "name": "目標", "data_type": "text", "horizontal_align": "right"},
                {"key": "已達成", "name": "已達成", "data_type": "text", "horizontal_align": "right"},
                {"key": "達成率", "name": "達成率", "data_type": "text", "horizontal_align": "right"},
            ],
            "rows": rows_data,
        })
    
    # 口徑
    components.append({"type": "text", "content": f"<font color='grey'>📋 數據口徑: 銷售首銷 | 數據來源: 飛書自動拉取 | 更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}</font>"})
    
    return {
        "card": {
            "title": f"📊 {product_name}首銷激活進展",
            "subtitle": f"報告日期 {datetime.now().strftime('%Y-%m-%d')} | 數據口徑: 銷售首銷",
            "components": components,
        }
    }

if __name__ == "__main__":
    # 從 stdin 讀取飛書 cells 數據
    data = json.load(sys.stdin)
    card = build_card_from_feishu(data)
    if card:
        print(json.dumps(card, ensure_ascii=False))
    else:
        print(json.dumps({"error": "無法生成卡片"}))
