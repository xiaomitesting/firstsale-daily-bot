#!/usr/bin/env python3
"""
飛書表格 → 首銷日報卡片生成器
用法：python3 feishu2report.py <feishu_url> [--sheet-id 2MqyRg]
"""

import json, re, sys, subprocess, os
from datetime import datetime

# ===== 配置 =====
# 格式：{ sheet_id: { 字段名: cell_range } }
# 支持的字段：target, achieved, rate, time_progress, progress_gap, prev_gen, yoy
#             daily_so (日期行範圍, 達成行範圍)
#             channels (行範圍, 列C:D=渠道名, E=目標, F=達成)
SHEET_CONFIGS = {
    "2MqyRg": {  # LEEDS 首销目标跟进
        "name": "LEEDS",
        "summary": {
            "target": "E2",
            "achieved": "F2",
            "rate": "G2",
            "time_progress": "H2",
            "progress_gap": "I2",
            "prev_gen": "J2",
            "yoy": "K2",
        },
        "daily_so": {
            "dates_row": "A1:AJ1",      # 第1行是日期
            "values_row": "L2:AJ2",     # 第2行是達成
            "prev_row": "AT2:BR2",      # 上代達成（如果有）
        },
        "channels": {
            "range": "C8:F15",          # 渠道數據
        },
        "sub_channels": {
            "range": "C16:F30",         # 子渠道
        },
        "products": {
            "range": "A31:F84",         # 產品拆分
        },
    },
}

def parse_feishu_url(url):
    """解析飛書鏈接，提取 spreadsheet_token 和 sheet_id"""
    # 支持格式：
    # https://xiaomi.feishu.cn/wiki/xxxxx?sheet=yyyyy
    # https://xiaomi.feishu.cn/sheets/xxxxx?sheet=yyyyy
    m = re.search(r'feishu\.cn/(?:wiki|sheets)/([A-Za-z0-9_-]+)', url)
    if not m:
        raise ValueError(f"無法識別飛書鏈接: {url}")
    token = m.group(1)
    
    # 提取 sheet_id
    sheet_match = re.search(r'[?&]sheet=([A-Za-z0-9_]+)', url)
    sheet_id = sheet_match.group(1) if sheet_match else None
    
    # 判斷是 wiki 還是 sheets
    is_wiki = '/wiki/' in url
    
    return {
        "token": token,
        "sheet_id": sheet_id,
        "is_wiki": is_wiki,
        "type": "wiki" if is_wiki else "sheets",
    }

def resolve_wiki_token(wiki_token):
    """Wiki token → obj_token (sheets token)"""
    result = subprocess.run(
        ["node", "/root/.openclaw/bin/lark-cli.js", "wiki", "+node-get", "--node-token", wiki_token],
        capture_output=True, text=True, timeout=15
    )
    data = json.loads(result.stdout)
    if not data.get("ok"):
        raise ValueError(f"Wiki 解析失敗: {data}")
    obj_token = data["data"]["obj_token"]
    obj_type = data["data"]["obj_type"]
    if obj_type != "sheet":
        raise ValueError(f"Wiki 指向的不是電子表格 (type={obj_type})")
    return obj_token

def read_cells(spreadsheet_token, sheet_id, cell_range):
    """讀取飛書表格指定範圍的值"""
    result = subprocess.run(
        ["node", "/root/.openclaw/bin/lark-cli.js", "sheets", "+cells-get",
         "--spreadsheet-token", spreadsheet_token,
         "--sheet-id", sheet_id,
         "--range", cell_range,
         "--include", "value"],
        capture_output=True, text=True, timeout=30
    )
    data = json.loads(result.stdout)
    if not data.get("ok"):
        raise ValueError(f"讀取失敗: {data}")
    return data["data"]

def extract_value(cell_data, cell_ref):
    """從 cells 數據中提取指定單元格的值"""
    ranges = cell_data.get("ranges", [])
    for r in ranges:
        col_indices = r.get("col_indices", [])
        row_indices = r.get("row_indices", [])
        cells = r.get("cells", [])
        for ri, row in enumerate(cells):
            for ci, cell in enumerate(row):
                actual_col = col_indices[ci] if ci < len(col_indices) else ""
                actual_row = row_indices[ri] if ri < len(row_indices) else 0
                if f"{actual_col}{actual_row}" == cell_ref:
                    val = cell.get("value", "")
                    # 清理數字
                    val = val.replace(",", "").replace("%", "").strip()
                    return val
    return None

def extract_range_values(cell_data):
    """從 cells 數據中提取一維數值列表"""
    values = []
    ranges = cell_data.get("ranges", [])
    for r in ranges:
        cells = r.get("cells", [])
        for row in cells:
            for cell in row:
                val = cell.get("value", "")
                val = val.replace(",", "").replace("%", "").strip()
                values.append(val)
    return values

def parse_num(s):
    """安全數字解析"""
    if not s or s in ("—", "-", "N/A", "/"):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def parse_date_header(s):
    """解析日期標題如 20260807"""
    s = str(s).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[4:6]}/{s[6:8]}"  # → "08/07"
    return s

def build_report(url, sheet_id_override=None):
    """主流程：URL → 飛書卡片 JSON"""
    info = parse_feishu_url(url)
    
    # 解析 wiki token
    if info["is_wiki"]:
        spreadsheet_token = resolve_wiki_token(info["token"])
    else:
        spreadsheet_token = info["token"]
    
    # 確定 sheet_id
    sheet_id = sheet_id_override or info["sheet_id"]
    if not sheet_id:
        raise ValueError("鏈接中未指定 sheet_id，請用 --sheet-id 參數指定")
    
    # 讀取配置
    config = SHEET_CONFIGS.get(sheet_id)
    if not config:
        raise ValueError(f"未知的 sheet_id: {sheet_id}，請先在 SHEET_CONFIGS 中添加配置")
    
    product_name = config["name"]
    
    print(f"📊 正在讀取 {product_name} 數據...")
    
    # 1. 讀取核心指標
    summary = {}
    for field, cell in config["summary"].items():
        cell_data = read_cells(spreadsheet_token, sheet_id, cell)
        val = extract_value(cell_data, cell)
        summary[field] = parse_num(val) if field != "name" else val
    print(f"  ✅ 核心指標: 目標={summary.get('target')}, 達成={summary.get('achieved')}, 達成率={summary.get('rate')}%")
    
    # 2. 讀取每日SO
    daily_dates = []
    daily_values = []
    daily_prev = []
    
    dates_data = read_cells(spreadsheet_token, sheet_id, config["daily_so"]["dates_row"])
    dates_raw = extract_range_values(dates_data)
    daily_dates = [parse_date_header(d) for d in dates_raw if d]
    
    values_data = read_cells(spreadsheet_token, sheet_id, config["daily_so"]["values_row"])
    daily_values = [parse_num(v) for v in extract_range_values(values_data)]
    
    # 讀取上代數據（如果有）
    try:
        prev_data = read_cells(spreadsheet_token, sheet_id, config["daily_so"]["prev_row"])
        daily_prev = [parse_num(v) for v in extract_range_values(prev_data)]
    except:
        daily_prev = []
    
    print(f"  ✅ 每日SO: {len(daily_dates)} 天")
    
    # 3. 讀取渠道數據
    channels = []
    ch_data = read_cells(spreadsheet_token, sheet_id, config["channels"]["range"])
    ch_ranges = ch_data.get("ranges", [])
    for r in ch_ranges:
        cells = r.get("cells", [])
        col_indices = r.get("col_indices", [])
        row_indices = r.get("row_indices", [])
        for ri, row in enumerate(cells):
            # 列C=大渠道, D=子渠道, E=目標, F=達成
            c_val = row[0].get("value", "") if len(row) > 0 else ""
            d_val = row[1].get("value", "") if len(row) > 1 else ""
            e_val = row[2].get("value", "").replace(",", "") if len(row) > 2 else ""
            f_val = row[3].get("value", "").replace(",", "") if len(row) > 3 else ""
            
            # 合計行（D="合计"）才是渠道總計
            if d_val == "合计":
                name = c_val  # 大渠道名
                channels.append({
                    "name": name,
                    "target": parse_num(e_val),
                    "achieved": parse_num(f_val),
                })
            elif c_val and not d_val:
                # 第一行有渠道名但無子渠道名（如"电商"行）
                pass  # 跳過，等 D="合计" 時再取
    
    print(f"  ✅ 渠道: {len(channels)} 個")
    
    # 4. 組裝卡片
    card = build_card_json(product_name, summary, daily_dates, daily_values, daily_prev, channels)
    
    return card

def build_card_json(product_name, summary, dates, values, prev_values, channels):
    """生成飛書卡片 JSON"""
    s = summary
    components = []
    
    # KPI 指標卡
    kpi_items = []
    if s.get("target"): kpi_items.append({"title": "首銷目標", "value": f"{int(s['target']):,}"})
    if s.get("achieved"): kpi_items.append({"title": "已達成", "value": f"{int(s['achieved']):,}"})
    if s.get("rate"): kpi_items.append({"title": "達成率", "value": f"{s['rate']}%"})
    if s.get("progress_gap"): kpi_items.append({"title": "進度落差", "value": f"{s['progress_gap']}pp"})
    if s.get("prev_gen"): kpi_items.append({"title": "上代同期", "value": f"{int(s['prev_gen']):,}"})
    if s.get("yoy"): kpi_items.append({"title": "同比", "value": f"{s['yoy']}%"})
    
    if kpi_items:
        components.append({"type": "kpi_group", "items": kpi_items})
    
    # 每日SO趨勢
    if dates and values:
        # 只取有值的部分
        valid = [(d, v) for d, v in zip(dates, values) if v is not None and v > 0]
        if valid:
            chart_data = []
            for d, v in valid:
                chart_data.append({"date": d, "value": v, "series": product_name})
            for i, (d, v) in enumerate(valid):
                if i < len(prev_values) and prev_values[i]:
                    chart_data.append({"date": d, "value": prev_values[i], "series": "上代"})
            
            components.append({"type": "text", "content": "**📈 每日SO趨勢**", "text_size": "heading-4"})
            components.append({
                "type": "line", "x": "date", "y": "value", "series": "series",
                "data": chart_data, "height": "280px"
            })
    
    # 渠道側
    if channels:
        total_target = sum(c["target"] or 0 for c in channels)
        total_achieved = sum(c["achieved"] or 0 for c in channels)
        
        components.append({"type": "text", "content": "**📊 渠道側**", "text_size": "heading-4"})
        
        ch_rows = []
        for ch in channels:
            rate = (ch["achieved"] / ch["target"] * 100) if ch["target"] and ch["achieved"] else None
            ch_rows.append({
                "渠道": ch["name"],
                "目標": f"{int(ch['target']):,}" if ch["target"] else "—",
                "已達成": f"{int(ch['achieved']):,}" if ch["achieved"] else "—",
                "達成率": f"{rate:.1f}%" if rate else "—",
            })
        
        # 合計行
        total_rate = (total_achieved / total_target * 100) if total_target else None
        ch_rows.append({
            "渠道": "📊 合計",
            "目標": f"{int(total_target):,}",
            "已達成": f"{int(total_achieved):,}",
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
            "rows": ch_rows,
        })
    
    # 口徑說明
    components.append({"type": "text", "content": f"<font color='grey'>📋 數據口徑: 銷售首銷 | 數據來源: 飛書表格自動拉取 | 更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}</font>"})
    
    # 組裝
    report_date = datetime.now().strftime("%Y-%m-%d")
    
    return {
        "card": {
            "title": f"📊 {product_name}首銷激活進展",
            "subtitle": f"報告日期 {report_date} | 數據口徑: 銷售首銷",
            "components": components,
        }
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="飛書表格 → 首銷日報卡片")
    parser.add_argument("url", help="飛書表格鏈接")
    parser.add_argument("--sheet-id", help="Sheet ID (從 URL ?sheet=xxx 取)", default=None)
    parser.add_argument("--output", "-o", default="output/card.json", help="輸出路徑")
    args = parser.parse_args()
    
    card = build_report(args.url, args.sheet_id)
    
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 卡片已生成: {args.output}")
    print(json.dumps(card, ensure_ascii=False, indent=2))
