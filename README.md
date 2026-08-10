# P12 首銷日報機器人

把飛書表格貼進去，自動生成首銷日報卡片。

## 快速開始

```bash
# 1. 安裝依賴（僅需 pyperclip）
pip install -r requirements.txt

# 2. 貼入數據並生成卡片
python run.py --paste

# 3. 或者指定數據文件
python run.py --file examples/sample.tsv
```

## 數據輸入方式

### 方式一：直接貼上（推薦）

1. 在飛書表格中選中數據區域，Ctrl+C 複製
2. 執行 `python run.py --paste`
3. 自動解析並生成卡片

### 方式二：TSV 文件

從飛書表格複製後，粘貼到文本文件保存為 `.tsv`，然後：

```bash
python run.py --file your_data.tsv
```

### 方式三：JSON 文件

```bash
python run.py --file your_data.json
```

## 數據格式

### TSV 格式（飛書表格直接貼上）

第一行是表頭，後續行是數據。支持以下列名（中英文均可）：

| 列名（中文） | 列名（英文） | 說明 | 必填 |
|-------------|-------------|------|------|
| 指標 | metric | 指標名稱 | ✅ |
| 數值 | value | 對應數值 | ✅ |

**必須包含的指標行：**

```
指標	數值
首銷目標	19456
已達成	15600
落后時間進度	16.8
上代同期	15600
YOY	85.8
時間進度	97.0
首銷日期	2026-05-29
報告日期	2026-06-29
DAY	32
```

**可選的每日 SO 數據（折線圖用）：**

```
日期	SO	上代SO
5/29	749	868
5/30	1400	1665
...
```

**可選的產品側數據：**

```
產品	目標	已達成	YOY
P12U	11674	9530	60.9
P12A	7782	6070	31.7
```

**可選的渠道側數據：**

```
渠道	目標	已達成	YOY
米網	2608	2092	80.2
米店	4472	3461	77.4
運營商	7266	6100	83.9
KA	4238	3332	78.6
GC&澳門	872	615	70.5
```

### JSON 格式

見 `examples/sample.json`

## 輸出

- 卡片 JSON 文件：`output/card.json`
- 終端打印卡片 JSON（可直接用於飛書發送）

## 自定義

- 修改 `templates/p12_template.json` 調整卡片樣式
- 修改 `src/report.py` 中的映射邏輯

## 文件結構

```
firstsale-daily-bot/
├── README.md
├── requirements.txt
├── run.py                  # 入口
├── src/
│   ├── __init__.py
│   ├── parser.py           # 數據解析（TSV/JSON）
│   ├── report.py           # 報告生成邏輯
│   └── card.py             # 飛書卡片構建
├── templates/
│   └── p12_template.json   # 卡片模板
├── examples/
│   ├── sample.tsv          # 示例 TSV
│   └── sample.json         # 示例 JSON
└── output/                 # 輸出目錄
```
