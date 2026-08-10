"""首銷日報機器人 - 飛書卡片構建

將解析後的數據轉為飛書互動卡片 JSON。
"""
import json
from typing import Any


def pct_str(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{val:+.1f}%" if val < 0 else f"+{val:.1f}%"


def num_str(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{val:,.0f}"


def safe_div(a, b):
    if b is None or b == 0:
        return None
    return a / b * 100


def build_card(data: dict[str, Any]) -> dict:
    """從解析後的數據構建飛書卡片 config"""
    summary = data.get("summary", {})
    daily = data.get("daily_so", {})
    products = data.get("product_breakdown", {})
    channels = data.get("channel_breakdown", [])
    configs = data.get("config_mix", {})
    colors = data.get("color_mix", {})

    components = []

    # ===== 1. KPI 指標卡 =====
    target = summary.get("target")
    achieved = summary.get("achieved")
    achv_rate = safe_div(achieved, target) or summary.get("achievement_rate")
    behind = summary.get("behind_time_progress")
    progress_gap = summary.get("progress_gap")
    prev_gen = summary.get("previous_gen_total")
    yoy = summary.get("yoy")

    kpi_items = []
    if target is not None:
        kpi_items.append({"title": "首銷目標", "value": num_str(target)})
    if achieved is not None:
        kpi_items.append({"title": "已達成", "value": num_str(achieved)})
    if achv_rate is not None:
        kpi_items.append({"title": "達成率", "value": f"{achv_rate:.1f}%"})
    if behind is not None:
        kpi_items.append({"title": "落後時間進度", "value": f"{behind:.1f}pp"})
    if progress_gap is not None:
        kpi_items.append({"title": "進度落差", "value": f"{progress_gap:.1f}%"})
    if prev_gen is not None:
        kpi_items.append({"title": "上代同期", "value": num_str(prev_gen)})
    if yoy is not None:
        kpi_items.append({"title": "YOY", "value": f"{yoy:.1f}%"})

    if kpi_items:
        components.append({"type": "kpi_group", "items": kpi_items})

    # ===== 2. 每日SO趨勢圖 =====
    dates = daily.get("dates", [])
    current_gen = daily.get("current_gen", [])
    previous_gen = daily.get("previous_gen", [])

    if dates and current_gen:
        title = summary.get("title", "P12系列")
        chart_data = []
        for i, d in enumerate(dates):
            chart_data.append({"date": d, "value": current_gen[i] if i < len(current_gen) else 0, "series": title})
            if i < len(previous_gen):
                chart_data.append({"date": d, "value": previous_gen[i], "series": "上代"})

        components.append({
            "type": "text",
            "content": "**📈 每日SO趨勢**",
            "text_size": "heading-4"
        })
        components.append({
            "type": "line",
            "x": "date",
            "y": "value",
            "series": "series",
            "data": chart_data,
            "height": "280px"
        })

    # ===== 3. 產品側 =====
    product_rows = []
    for pname, pdata in products.items():
        if pname.startswith("_"):
            continue
        p_target = pdata.get("target")
        p_achieved = pdata.get("achieved")
        p_rate = safe_div(p_achieved, p_target)
        p_yoy = pdata.get("yoy")
        product_rows.append({
            "product": pname,
            "target": num_str(p_target) if p_target else "—",
            "achieved": num_str(p_achieved) if p_achieved else "—",
            "rate": f"{p_rate:.1f}%" if p_rate else "—",
            "yoy": f"{p_yoy:.1f}%" if p_yoy else "—"
        })

    if product_rows:
        components.append({"type": "text", "content": "**📱 產品側**", "text_size": "heading-4"})
        components.append({
            "type": "table",
            "columns": [
                {"key": "product", "name": "產品"},
                {"key": "target", "name": "目標", "data_type": "text", "horizontal_align": "right"},
                {"key": "achieved", "name": "已達成", "data_type": "text", "horizontal_align": "right"},
                {"key": "rate", "name": "達成率", "data_type": "text", "horizontal_align": "right"},
                {"key": "yoy", "name": "YOY", "data_type": "text", "horizontal_align": "right"}
            ],
            "rows": product_rows
        })

    # 產品佔比
    mix = products.get("_mix", {})
    if mix:
        components.append({
            "type": "text",
            "content": f"**產品佔比**：{mix.get('current', '—')} vs 上代 {mix.get('previous', '—')}"
        })

    # ===== 4. 配置佔比 =====
    if configs.get("current"):
        components.append({"type": "text", "content": "**⚙️ 配置佔比**", "text_size": "heading-4"})
        all_cfgs = sorted(set(c["name"] for c in configs["current"]) | set(c["name"] for c in configs.get("previous", [])))
        config_rows = []
        for cfg_name in all_cfgs:
            curr = next((c["value"] for c in configs["current"] if c["name"] == cfg_name), None)
            prev = next((c["value"] for c in configs.get("previous", []) if c["name"] == cfg_name), None)
            config_rows.append({
                "config": cfg_name,
                "本代": f"{curr:.1f}%" if curr is not None else "—",
                "上代": f"{prev:.1f}%" if prev is not None else "—"
            })
        if config_rows:
            components.append({
                "type": "table",
                "columns": [
                    {"key": "config", "name": "配置"},
                    {"key": "本代", "name": "本代", "data_type": "text", "horizontal_align": "right"},
                    {"key": "上代", "name": "上代", "data_type": "text", "horizontal_align": "right"}
                ],
                "rows": config_rows
            })

    # ===== 5. 顏色佔比 =====
    if colors.get("current"):
        components.append({"type": "text", "content": "**🎨 顏色佔比**", "text_size": "heading-4"})
        all_colors = sorted(set(c["name"] for c in colors["current"]) | set(c["name"] for c in colors.get("previous", [])))
        color_rows = []
        for cname in all_colors:
            curr = next((c["value"] for c in colors["current"] if c["name"] == cname), None)
            prev = next((c["value"] for c in colors.get("previous", []) if c["name"] == cname), None)
            color_rows.append({
                "color": cname,
                "本代": f"{curr:.1f}%" if curr is not None else "—",
                "上代": f"{prev:.1f}%" if prev is not None else "—"
            })
        if color_rows:
            components.append({
                "type": "table",
                "columns": [
                    {"key": "color", "name": "顏色"},
                    {"key": "本代", "name": "本代", "data_type": "text", "horizontal_align": "right"},
                    {"key": "上代", "name": "上代", "data_type": "text", "horizontal_align": "right"}
                ],
                "rows": color_rows
            })

    # ===== 6. 渠道側 =====
    if channels:
        components.append({"type": "text", "content": "**📊 渠道側**", "text_size": "heading-4"})
        ch_rows = []
        total_target = 0
        total_achieved = 0
        for ch in channels:
            ch_target = ch.get("target")
            ch_achieved = ch.get("achieved")
            ch_rate = safe_div(ch_achieved, ch_target)
            ch_yoy = ch.get("yoy")
            ch_rows.append({
                "channel": ch["name"],
                "target": num_str(ch_target) if ch_target else "—",
                "achieved": num_str(ch_achieved) if ch_achieved else "—",
                "rate": f"{ch_rate:.1f}%" if ch_rate else "—",
                "yoy": f"{ch_yoy:.1f}%" if ch_yoy else "—"
            })
            if ch_target:
                total_target += ch_target
            if ch_achieved:
                total_achieved += ch_achieved

        # 合計行
        total_rate = safe_div(total_achieved, total_target)
        ch_rows.append({
            "channel": "📊 合計",
            "target": num_str(total_target) if total_target else "—",
            "achieved": num_str(total_achieved) if total_achieved else "—",
            "rate": f"{total_rate:.1f}%" if total_rate else "—",
            "yoy": "—"
        })

        components.append({
            "type": "table",
            "columns": [
                {"key": "channel", "name": "渠道"},
                {"key": "target", "name": "目標", "data_type": "text", "horizontal_align": "right"},
                {"key": "achieved", "name": "已達成", "data_type": "text", "horizontal_align": "right"},
                {"key": "rate", "name": "達成率", "data_type": "text", "horizontal_align": "right"},
                {"key": "yoy", "name": "YOY", "data_type": "text", "horizontal_align": "right"}
            ],
            "rows": ch_rows
        })

    # ===== 7. 口徑說明 =====
    launch = summary.get("launch_date", "")
    footnote = data.get("footnote", f"首銷期: {launch} 起 | 數據口徑: 銷售激活 | 數據來源: 國際BI")
    components.append({"type": "text", "content": f"<font color='grey'>📋 {footnote}</font>"})

    # ===== 組裝卡片 =====
    title = summary.get("title", "P12系列")
    day_number = summary.get("day_number")
    report_date = summary.get("report_date", "")
    time_progress = summary.get("time_progress")

    subtitle_parts = []
    if day_number:
        subtitle_parts.append(f"DAY {day_number}")
    if report_date:
        subtitle_parts.append(str(report_date))
    if time_progress:
        subtitle_parts.append(f"時間進度{time_progress}%")

    return {
        "card": {
            "title": f"📊 {title}首銷激活進展",
            "subtitle": " | ".join(subtitle_parts),
            "components": components
        }
    }


def generate_text(data: dict[str, Any], title: str = "") -> str:
    """從解析後的數據生成純文本日報（可複製發群）"""
    s = data.get("summary", {})
    if not title:
        title = s.get("title", "P12系列")
    lines = []

    # 標題行：P12系列首銷激活進展DAY 32 - 6/29（時間進度97%）
    header = f"{title}首銷激活進展"
    if s.get("day_number"):
        header += f"DAY {s['day_number']}"
    date_part = ""
    if s.get("report_date"):
        date_str = str(s["report_date"])
        import re
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
        if m:
            date_part = f"{int(m.group(2))}/{int(m.group(3))}"
        else:
            date_part = date_str
    tp_part = ""
    if s.get("time_progress"):
        tp_part = f"時間進度{s['time_progress']}%"
    # 拼接：header - date_part（tp_part）
    if date_part and tp_part:
        lines.append(f"{header} - {date_part}（{tp_part}）")
    elif date_part:
        lines.append(f"{header} - {date_part}（）")
    elif tp_part:
        lines.append(f"{header}（{tp_part}）")
    else:
        lines.append(header)
    lines.append("")

    # 銷售數據摘要
    summary_parts = []
    target = s.get("target")
    achieved = s.get("achieved")
    if target is not None:
        summary_parts.append(f"首銷目標{num_str(target)}台")
    if achieved is not None:
        summary_parts.append(f"首銷達成{num_str(achieved)}台")
    rate = s.get("achievement_rate") or safe_div(achieved, target)
    if rate is not None:
        summary_parts.append(f"首銷達成率{rate:.0f}%")
    behind = s.get("behind_time_progress")
    if behind is not None:
        summary_parts.append(f"落後時間進度{behind:.0f}pp")
    prev_gen = s.get("previous_gen_total")
    if prev_gen is not None:
        summary_parts.append(f"上代同期達成{num_str(prev_gen)}台")
    yoy = s.get("yoy")
    if yoy is not None:
        summary_parts.append(f"YOY {yoy:+.0f}%")
    lines.append("• 銷售數據：" + "，".join(summary_parts))
    lines.append("")

    # 產品側
    products = {k: v for k, v in data.get("product_breakdown", {}).items() if not k.startswith("_")}
    if products:
        lines.append("• 產品側：")
        for pname, pdata in products.items():
            parts = []
            p_target = pdata.get("target")
            p_achieved = pdata.get("achieved")
            if p_target is not None:
                parts.append(f"目標{num_str(p_target)}台")
            if p_achieved is not None:
                parts.append(f"達成{num_str(p_achieved)}台")
            p_rate = safe_div(p_achieved, p_target)
            if p_rate is not None:
                parts.append(f"達成率{p_rate:.0f}%")
            p_yoy = pdata.get("yoy")
            if p_yoy is not None:
                parts.append(f"YOY {p_yoy:+.0f}%")
            lines.append(f"  ◦ {pname}：{"，".join(parts)}")
        mix = data.get("product_breakdown", {}).get("_mix", {})
        if mix:
            lines.append("  ◦ 產品佔比：")
            if mix.get("current"):
                lines.append(f"    ▪ {mix['current']}")
            if mix.get("previous"):
                lines.append(f"      • 上代佔比：{mix['previous']}")
        lines.append("")

    # 配置佔比
    configs = data.get("config_mix", {})
    if configs.get("current"):
        lines.append("  ◦ 配置佔比：")
        for cfg in configs["current"]:
            lines.append(f"    ▪ {cfg['name']}：{cfg['value']:.0f}%")
        for cfg in configs.get("previous", []):
            lines.append(f"      • 上代佔比：{cfg['name']}：{cfg['value']:.0f}%")
        lines.append("")

    # 顏色佔比
    colors = data.get("color_mix", {})
    if colors.get("current"):
        lines.append("  ◦ 顏色佔比：")
        for c in colors["current"]:
            lines.append(f"    ▪ {c['name']}：{c['value']:.0f}%")
        for c in colors.get("previous", []):
            lines.append(f"      • 上代佔比：{c['name']}：{c['value']:.0f}%")
        lines.append("")

    # 渠道側
    channels = data.get("channel_breakdown", [])
    if channels:
        lines.append("• 渠道側：")
        for ch in channels:
            parts = []
            ch_target = ch.get("target")
            ch_achieved = ch.get("achieved")
            if ch_target is not None:
                parts.append(f"目標{num_str(ch_target)}台")
            if ch_achieved is not None:
                parts.append(f"達成{num_str(ch_achieved)}台")
            ch_rate = safe_div(ch_achieved, ch_target)
            if ch_rate is not None:
                parts.append(f"目標達成率{ch_rate:.0f}%")
            ch_yoy = ch.get("yoy")
            if ch_yoy is not None:
                parts.append(f"YOY {ch_yoy:+.0f}%")
            lines.append(f"  ◦ {ch['name']}：{"，".join(parts)}")
        lines.append("")

    return "\n".join(lines)
