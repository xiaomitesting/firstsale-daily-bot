# 首銷日報機器人

貼入飛書表格數據，一鍵生成首銷日報飛書卡片。

🔗 **[線上演示](https://xiaomitesting.github.io/firstsale-daily-bot/)**

## 功能

- ✅ 飛書表格 TSV 直接貼上
- ✅ 文件上傳（TSV / JSON）
- ✅ 預設模板（手機 / 平板）
- ✅ 卡片實時預覽
- ✅ 一鍵複製 JSON
- ✅ 下載 JSON 文件
- ✅ 輸出 Markdown 格式
- ✅ 通用：不限產品線，任意首銷日報都能用

## 數據格式

支持多段數據，每段有獨立表頭：

| 段落 | 表頭 | 說明 | 必填 |
|------|------|------|------|
| 核心指標 | `指標 數值` | 首銷目標、已達成、YOY 等 | ✅ |
| 每日 SO | `日期 SO 上代SO` | 折線圖數據 | 🟡 |
| 產品側 | `產品 目標 已達成 YOY` | 各型號拆分 | 🟡 |
| 渠道側 | `渠道 目標 已達成 YOY` | 各渠道拆分 | 🟡 |
| 配置佔比 | `配置 本代 上代` | 存儲配置 | 🟡 |
| 顏色佔比 | `顏色 本代 上代` | 顏色分佈 | 🟡 |

## 快速開始

### 方式一：線上市場（推薦）

直接訪問 https://xiaomitesting.github.io/firstsale-daily-bot/

### 方式二：本地運行

```bash
# 進入 web 目錄
cd web

# 啟動本地服務器
python3 -m http.server 8080

# 打開瀏覽器訪問
open http://localhost:8080
```

### 方式三：Python CLI

```bash
pip install -r requirements.txt
python run.py --file examples/sample.tsv
```

## 使用流程

1. 從飛書表格選中數據 → `Ctrl+C` 複製
2. 打開網站 → 粘貼到輸入框
3. 點擊「生成日報」
4. 右側預覽卡片效果
5. 點擊「複製 JSON」→ 在飛書機器人中發送

## 技術棧

- 純前端：HTML + CSS + JavaScript（無後端）
- 部署：GitHub Pages
- 卡片格式：飛書互動卡片 Schema 2.0

## 文件結構

```
firstsale-daily-bot/
├── web/                    # 網站（GitHub Pages）
│   ├── index.html          # 主頁面
│   ├── style.css           # 樣式
│   └── app.js              # 核心邏輯
├── src/                    # Python CLI
│   ├── parser.py           # TSV/JSON 解析
│   └── card.py             # 卡片構建
├── examples/               # 示例數據
├── run.py                  # CLI 入口
└── README.md
```

## License

MIT
