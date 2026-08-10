#!/usr/bin/env python3
"""
P12 首銷日報機器人

用法:
  python run.py --paste              # 從剪貼板讀取飛書表格數據
  python run.py --file data.tsv      # 從 TSV 文件讀取
  python run.py --file data.json     # 從 JSON 文件讀取
  python run.py --file data.tsv -o output/card.json  # 指定輸出路徑
"""
import argparse, json, sys, os

# 確保 src 可導入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.parser import parse_clipboard, parse_file
from src.card import build_card, generate_text


def main():
    parser = argparse.ArgumentParser(description="P12 首銷日報機器人")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--paste", action="store_true", help="從剪貼板讀取數據")
    group.add_argument("--file", "-f", help="數據文件路徑（TSV 或 JSON）")
    parser.add_argument("--output", "-o", default="output/card.json", help="輸出路徑")
    parser.add_argument("--text", action="store_true", help="輸出純文本日報（可複製發群）")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 輸出")
    args = parser.parse_args()

    # 1. 解析數據
    try:
        if args.paste:
            data = parse_clipboard()
        else:
            data = parse_file(args.file)
    except Exception as e:
        print(f"❌ 數據解析失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 驗證必需字段
    summary = data.get("summary", {})
    missing = []
    if "target" not in summary:
        missing.append("首銷目標")
    if "achieved" not in summary:
        missing.append("已達成")
    if missing:
        print(f"⚠️  缺少必需指標: {', '.join(missing)}", file=sys.stderr)
        print("請確保數據中包含以下行:", file=sys.stderr)
        print("  指標\t數值", file=sys.stderr)
        print("  首銷目標\t19456", file=sys.stderr)
        print("  已達成\t15600", file=sys.stderr)
        sys.exit(1)

    # 3. 構建卡片或文本
    if args.text:
        try:
            text = generate_text(data)
            # 輸出到文件或 stdout
            if args.output and args.output != "output/card.json":
                output_dir = os.path.dirname(args.output)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"✅ 純文本日報已生成: {args.output}")
            else:
                print(text)
        except Exception as e:
            print(f"❌ 文本生成失敗: {e}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        card_config = build_card(data)
    except Exception as e:
        print(f"❌ 卡片構建失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 4. 輸出
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    indent = 2 if args.pretty else None
    card_json = json.dumps(card_config, ensure_ascii=False, indent=indent)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(card_json)

    print(f"✅ 卡片 JSON 已生成: {args.output}")

    # 如果沒有 data-card 的 build_card.py，直接輸出 raw config
    # 有 build_card.py 時可以進一步轉為完整飛書卡片
    build_card_path = os.path.expanduser("~/.openclaw/skills/data-card/scripts/build_card.py")
    if os.path.exists(build_card_path):
        import subprocess
        result = subprocess.run(
            ["python3", build_card_path, "--message", "-", "--version", "0.7.1"],
            input=card_json,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            full_card_path = args.output.replace(".json", "_full.json")
            with open(full_card_path, "w", encoding="utf-8") as f:
                f.write(result.stdout.strip())
            print(f"✅ 完整飛書卡片: {full_card_path}")
        else:
            print(f"⚠️  build_card.py 轉換失敗，已輸出 raw config", file=sys.stderr)


if __name__ == "__main__":
    main()
