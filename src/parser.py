"""首銷日報機器人 - 數據解析器

支持兩種輸入格式：
1. TSV（飛書表格直接貼上）
2. JSON（結構化數據）
"""
import json, re, sys
from pathlib import Path
from typing import Any


# ===== 指標名稱映射（中文 → 英文 key）=====
METRIC_ALIASES = {
    # 核心指標
    "首銷目標": "target",
    "目标": "target",
    "target": "target",
    "已達成": "achieved",
    "已达成": "achieved",
    "achieved": "achieved",
    "達成率": "achievement_rate",
    "达成率": "achievement_rate",
    "achievement_rate": "achievement_rate",
    "落后時間進度": "behind_time_progress",
    "落后时间进度": "behind_time_progress",
    "behind_time_progress": "behind_time_progress",
    "上代同期": "previous_gen_total",
    "previous_gen_total": "previous_gen_total",
    "YOY": "yoy",
    "yoy": "yoy",
    "時間進度": "time_progress",
    "时间进度": "time_progress",
    "time_progress": "time_progress",
    "首銷日期": "launch_date",
    "首销日期": "launch_date",
    "launch_date": "launch_date",
    "報告日期": "report_date",
    "报告日期": "report_date",
    "report_date": "report_date",
    "DAY": "day_number",
    "day": "day_number",
    "day_number": "day_number",
    "產品": "product_name",
    "产品": "product_name",
    "系列": "product_name",
    "title": "title",
    "標題": "title",
    "标题": "title",
    # 產品側
    "P12U": {"product": "P12U"},
    "P12A": {"product": "P12A"},
    "P12U目標": {"product": "P12U", "field": "target"},
    "P12A目標": {"product": "P12A", "field": "target"},
    "P12U已達成": {"product": "P12U", "field": "achieved"},
    "P12A已達成": {"product": "P12A", "field": "achieved"},
    "P12U_YOY": {"product": "P12U", "field": "yoy"},
    "P12A_YOY": {"product": "P12A", "field": "yoy"},
    "產品佔比": "product_mix",
    "产品占比": "product_mix",
    "product_mix": "product_mix",
    "上代佔比": "product_mix_prev",
    "上代占比": "product_mix_prev",
    "product_mix_prev": "product_mix_prev",
    # 配置/顏色
    "配置": "config",
    "配置佔比": "config_mix",
    "配置占比": "config_mix",
    "config_mix": "config_mix",
    "顏色": "color",
    "颜色": "color",
    "顏色佔比": "color_mix",
    "颜色占比": "color_mix",
    "color_mix": "color_mix",
}

# 渠道名稱映射
CHANNEL_ALIASES = {
    "米网": "米網",
    "米店": "米店",
    "運營商": "運營商",
    "运营商": "運營商",
    "KA": "KA",
    "GC": "GC&澳門",
    "GC&澳門": "GC&澳門",
    "gc": "GC&澳門",
}


def parse_tsv(text: str) -> dict[str, Any]:
    """解析 TSV 格式（飛書表格貼上）

    支持多段數據，用空行分隔：
    - 第一段：核心指標
    - 第二段（可選）：每日 SO
    - 第三段（可選）：產品側
    - 第四段（可選）：渠道側
    """
    lines = [l for l in text.strip().split("\n") if l.strip()]
    if not lines:
        raise ValueError("數據為空")

    # 按表頭偵測分段（飛書貼上可能沒有空行）
    segments = []
    current = []

    for line in lines:
        cols = [c.strip().lower() for c in line.split("\t")]
        first_col = cols[0]
        # 表頭判定：第一列精確匹配已知表頭詞，且列數 >= 2
        header_keywords = {"日期", "date", "產品", "产品", "渠道", "channel",
                          "配置", "config", "顏色", "颜色", "color"}
        is_header = first_col in header_keywords and len(cols) >= 2
        if is_header and current:
            segments.append(current)
            current = []
        current.append(line)
    if current:
        segments.append(current)

    result: dict[str, Any] = {
        "summary": {},
        "daily_so": {"dates": [], "current_gen": [], "previous_gen": []},
        "product_breakdown": {},
        "channel_breakdown": [],
        "config_mix": {"current": [], "previous": []},
        "color_mix": {"current": [], "previous": []},
    }

    for seg in segments:
        _parse_segment(seg, result)

    return result


def _parse_segment(lines: list[str], result: dict):
    """解析一個數據段"""
    header = lines[0].split("\t")
    header = [h.strip() for h in header]

    # 判斷段落類型
    header_lower = [h.lower() for h in header]

    if "日期" in header or "date" in header_lower:
        _parse_daily_so(header, lines[1:], result)
    elif any(p in " ".join(header) for p in ["P12U", "P12A", "产品", "產品"]):
        _parse_product(header, lines[1:], result)
    elif any(ch in " ".join(header) for ch in ["渠道", "channel", "米網", "米网", "KA"]):
        _parse_channel(header, lines[1:], result)
    elif "配置" in " ".join(header) or "config" in header_lower:
        _parse_config(header, lines[1:], result)
    elif "顏色" in " ".join(header) or "颜色" in " ".join(header) or "color" in header_lower:
        _parse_color(header, lines[1:], result)
    else:
        _parse_summary(header, lines[1:], result)


def _parse_summary(header: list[str], rows: list[str], result: dict):
    """解析核心指標段"""
    for row in rows:
        cols = row.split("\t")
        if len(cols) < 2:
            continue
        key = cols[0].strip()
        val = cols[1].strip()

        # 映射到英文 key
        eng = METRIC_ALIASES.get(key, key)

        if isinstance(eng, dict):
            # 產品側數據
            product = eng["product"]
            field = eng.get("field", "achieved")  # 默認當作 achieved
            if product not in result["product_breakdown"]:
                result["product_breakdown"][product] = {}
            result["product_breakdown"][product][field] = _parse_num(val)
        elif eng in ("product_mix",):
            result["product_breakdown"]["_mix"] = result["product_breakdown"].get("_mix", {})
            result["product_breakdown"]["_mix"]["current"] = val
        elif eng in ("product_mix_prev",):
            result["product_breakdown"]["_mix"] = result["product_breakdown"].get("_mix", {})
            result["product_breakdown"]["_mix"]["previous"] = val
        else:
            result["summary"][eng] = _parse_num(val) if eng != "launch_date" and eng != "report_date" and eng != "title" else val


def _parse_daily_so(header: list[str], rows: list[str], result: dict):
    """解析每日 SO 數據"""
    # 找列索引
    date_idx = _find_col(header, ["日期", "date"])
    so_idx = _find_col(header, ["SO", "so", "激活", "active"])
    prev_idx = _find_col(header, ["上代SO", "上代", "previous", "O代", "O12"])

    for row in rows:
        cols = row.split("\t")
        if len(cols) <= max(date_idx, so_idx):
            continue
        date = cols[date_idx].strip()
        so = _parse_num(cols[so_idx].strip())
        prev = _parse_num(cols[prev_idx].strip()) if prev_idx < len(cols) else None

        result["daily_so"]["dates"].append(date)
        result["daily_so"]["current_gen"].append(so)
        if prev is not None:
            result["daily_so"]["previous_gen"].append(prev)


def _parse_product(header: list[str], rows: list[str], result: dict):
    """解析產品側數據"""
    name_idx = _find_col(header, ["產品", "产品", "name", "系列"])
    target_idx = _find_col(header, ["目標", "目标", "target"])
    achieved_idx = _find_col(header, ["已達成", "已达成", "achieved", "SO"])
    yoy_idx = _find_col(header, ["YOY", "yoy", "同比"])

    for row in rows:
        cols = row.split("\t")
        if len(cols) <= max(name_idx, achieved_idx):
            continue
        name = cols[name_idx].strip()
        result["product_breakdown"][name] = {
            "target": _parse_num(cols[target_idx].strip()) if target_idx < len(cols) else None,
            "achieved": _parse_num(cols[achieved_idx].strip()),
            "yoy": _parse_num(cols[yoy_idx].strip()) if yoy_idx < len(cols) else None,
        }


def _parse_channel(header: list[str], rows: list[str], result: dict):
    """解析渠道側數據"""
    name_idx = _find_col(header, ["渠道", "channel", "名稱", "名称"])
    target_idx = _find_col(header, ["目標", "目标", "target"])
    achieved_idx = _find_col(header, ["已達成", "已达成", "achieved", "SO"])
    yoy_idx = _find_col(header, ["YOY", "yoy", "同比"])

    for row in rows:
        cols = row.split("\t")
        if len(cols) <= max(name_idx, achieved_idx):
            continue
        name = cols[name_idx].strip()
        name = CHANNEL_ALIASES.get(name, name)
        result["channel_breakdown"].append({
            "name": name,
            "target": _parse_num(cols[target_idx].strip()) if target_idx < len(cols) and cols[target_idx].strip() else None,
            "achieved": _parse_num(cols[achieved_idx].strip()),
            "yoy": _parse_num(cols[yoy_idx].strip()) if yoy_idx < len(cols) and cols[yoy_idx].strip() else None,
        })


def _parse_config(header: list[str], rows: list[str], result: dict):
    """解析配置佔比"""
    name_idx = _find_col(header, ["配置", "config", "名稱", "名称"])
    curr_idx = _find_col(header, ["本代", "當前", "current", "P12"])
    prev_idx = _find_col(header, ["上代", "O代", "previous", "O12"])

    for row in rows:
        cols = row.split("\t")
        if len(cols) <= max(name_idx, curr_idx):
            continue
        name = cols[name_idx].strip()
        curr_val = _parse_num(cols[curr_idx].strip())
        prev_val = _parse_num(cols[prev_idx].strip()) if prev_idx < len(cols) and cols[prev_idx].strip() else None

        result["config_mix"]["current"].append({"name": name, "value": curr_val})
        if prev_val is not None:
            result["config_mix"]["previous"].append({"name": name, "value": prev_val})


def _parse_color(header: list[str], rows: list[str], result: dict):
    """解析顏色佔比"""
    name_idx = _find_col(header, ["顏色", "颜色", "color", "名稱", "名称"])
    curr_idx = _find_col(header, ["本代", "當前", "current", "P12"])
    prev_idx = _find_col(header, ["上代", "O代", "previous", "O12"])

    for row in rows:
        cols = row.split("\t")
        if len(cols) <= max(name_idx, curr_idx):
            continue
        name = cols[name_idx].strip()
        curr_val = _parse_num(cols[curr_idx].strip())
        prev_val = _parse_num(cols[prev_idx].strip()) if prev_idx < len(cols) and cols[prev_idx].strip() else None

        result["color_mix"]["current"].append({"name": name, "value": curr_val})
        if prev_val is not None:
            result["color_mix"]["previous"].append({"name": name, "value": prev_val})


def _find_col(header: list[str], candidates: list[str]) -> int:
    """找列索引（精確匹配優先）"""
    # 第一輪：精確匹配
    for i, h in enumerate(header):
        h_clean = h.strip().lower()
        for c in candidates:
            if h_clean == c.lower():
                return i
    # 第二輪：包含匹配（但候選詞必須完全在列名中）
    for i, h in enumerate(header):
        h_clean = h.strip().lower()
        for c in candidates:
            cl = c.lower()
            if len(cl) >= 3 and cl in h_clean and h_clean != cl:
                return i
    return -1


def _parse_num(s: str) -> float | None:
    """解析數字"""
    if not s or s in ("—", "-", "N/A", "NA", ""):
        return None
    s = s.replace(",", "").replace("%", "").replace("+", "").strip()
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def parse_json(path: str) -> dict[str, Any]:
    """解析 JSON 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_file(path: str) -> dict[str, Any]:
    """根據文件後綴自動選擇解析器"""
    p = Path(path)
    if p.suffix.lower() == ".json":
        return parse_json(path)
    else:
        with open(path, "r", encoding="utf-8") as f:
            return parse_tsv(f.read())


def parse_clipboard() -> dict[str, Any]:
    """從剪貼板讀取數據"""
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text.strip():
            raise ValueError("剪貼板為空，請先從飛書表格複製數據")
        return parse_tsv(text)
    except ImportError:
        raise ImportError("需要安裝 pyperclip: pip install pyperclip")
