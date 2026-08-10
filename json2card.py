#!/usr/bin/env python3
"""
JSON 數據 → 首銷日報卡片
用法：python3 json2card.py data.json [--output output/card.json]

JSON 格式見 feishu_data_template.json
"""

import json, os, sys
from datetime import datetime

def parse_num(s):
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    s = str(s).replace(",", "").replace("%", "").strip()
    if not s or s in ("—", "-", "N/A", "/"): return None
    try: return float(s)
    except: return None

def build_card(data):
    """data: dict with name, summary, daily_so, channels"""
    components = []
    name = data.get("name", "產品")
    s = data.get("summary", {})
    
    # === KPI 指標卡 ===
    kpi = []
    if s.get("target") is not None: kpi.append({"title": "首銷目標", "value": f"{int(s['target']):,}"})
    if s.get("achieved") is not None: kpi.append({"title": "已達成", "value": f"{int(s['achieved']):,}"})
    rate = s.get("rate")
    if rate is not None:
        rate_str = str(rate).replace("%", "").strip()
        try: kpi.append({"title": "達成率", "value": f"{float(rate_str):.1f}%"})
        except: kpi.append({"title": "達成率", "value": str(rate)})
    gap = s.get("progress_gap")
    if gap is not None:
        gap_str = str(gap)
        gap_clean = gap_str.replace("pp", "").replace("%", "").strip()
        try: kpi.append({"title": "進度落差", "value": f"{float(gap_clean)}pp"})
        except: kpi.append({"title": "進度落差", "value": gap_str})
    if s.get("prev_gen") is not None: kpi.append({"title": "上代同期", "value": f"{int(s['prev_gen']):,}"})
    yoy = s.get("yoy")
    if yoy is not None:
        yoy_str = str(yoy).replace("%", "").strip()
        try: kpi.append({"title": "同比", "value": f"{float(yoy_str):.1f}%"})
        except: kpi.append({"title": "同比", "value": str(yoy)})
    
    if kpi:
        components.append({"type": "kpi_group", "items": kpi})
    
    # === 每日SO趨勢 ===
    dso = data.get("daily_so", {})
    dates = dso.get("dates", [])
    values = dso.get("values", [])
    prev = dso.get("prev_values", [])
    
    if dates and values:
        chart = []
        for i, d in enumerate(dates):
            v = values[i] if i < len(values) else 0
            if v and v > 0:
                chart.append({"date": d, "value": v, "series": name})
        for i, d in enumerate(dates):
            pv = prev[i] if i < len(prev) else 0
            if pv and pv > 0:
                chart.append({"date": d, "value": pv, "series": "上代"})
        
        if chart:
            components.append({"type": "text", "content": "**📈 每日SO趨勢**", "text_size": "heading-4"})
            components.append({
                "type": "line", "x": "date", "y": "value", "series": "series",
                "data": chart, "height": "280px"
            })
    
    # === 渠道側 ===
    channels = data.get("channels", [])
    if channels:
        components.append({"type": "text", "content": "**📊 渠道側**", "text_size": "heading-4"})
        
        total_t = sum(c.get("target") or 0 for c in channels)
        total_a = sum(c.get("achieved") or 0 for c in channels)
        
        rows = []
        for ch in channels:
            t = ch.get("target")
            a = ch.get("achieved")
            rate = (a / t * 100) if t and a else None
            rows.append({
                "渠道": ch.get("name", ""),
                "目標": f"{int(t):,}" if t else "—",
                "已達成": f"{int(a):,}" if a else "—",
                "達成率": f"{rate:.1f}%" if rate else "—",
            })
        
        total_rate = (total_a / total_t * 100) if total_t else None
        rows.append({
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
            "rows": rows,
        })
    
    # === 口徑 ===
    components.append({"type": "text", "content": f"<font color='grey'>📋 數據口徑: 銷售首銷 | 數據來源: 飛書表格自動拉取 | 更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}</font>"})
    
    report_date = data.get("report_date", datetime.now().strftime("%Y-%m-%d"))
    
    return {
        "card": {
            "title": f"📊 {name}首銷激活進展",
            "subtitle": f"報告日期 {report_date} | 數據口徑: 銷售首銷",
            "components": components,
        }
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JSON → 首銷日報卡片")
    parser.add_argument("input", help="JSON 數據文件")
    parser.add_argument("--output", "-o", default="output/card.json")
    args = parser.parse_args()
    
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    card = build_card(data)
    
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 卡片已生成: {args.output}")
    print(json.dumps(card, ensure_ascii=False, indent=2))
