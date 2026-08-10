/**
 * 首銷日報機器人 - 飛書數據代理服務器
 * 
 * 功能：接受飛書表格鏈接 → 讀取數據 → 返回 JSON
 * 啟動：node server.js
 * 端口：3900
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = 3900;

// ===== 讀取飛書憑證 =====
function getFeishuCredentials() {
  try {
    const configPath = path.join(process.env.HOME, '.openclaw/openclaw.json');
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    const feishu = config.channels?.feishu;
    if (!feishu?.appId || !feishu?.appSecret) {
      throw new Error('飛書憑證未配置');
    }
    return { appId: feishu.appId, appSecret: feishu.appSecret };
  } catch (e) {
    console.error('讀取飛書憑證失敗:', e.message);
    return null;
  }
}

// ===== HTTP 請求工具 =====
function httpRequest(options, postData = null) {
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(data);
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(15000, () => { req.destroy(); reject(new Error('Timeout')); });
    if (postData) req.write(postData);
    req.end();
  });
}

// ===== 獲取 tenant_access_token =====
let cachedToken = null;
let tokenExpiry = 0;

async function getTenantToken() {
  if (cachedToken && Date.now() < tokenExpiry) return cachedToken;
  
  const creds = getFeishuCredentials();
  if (!creds) throw new Error('飛書憑證未配置');
  
  const data = await httpRequest({
    hostname: 'open.feishu.cn',
    path: '/open-apis/auth/v3/tenant_access_token/internal',
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  }, JSON.stringify({ app_id: creds.appId, app_secret: creds.appSecret }));
  
  if (data.code !== 0) throw new Error(`獲取 token 失敗: ${data.msg}`);
  
  cachedToken = data.tenant_access_token;
  tokenExpiry = Date.now() + (data.expire - 300) * 1000; // 提前5分鐘刷新
  return cachedToken;
}

// ===== 解析飛書鏈接 =====
function parseFeishuUrl(inputUrl) {
  const parsed = url.parse(inputUrl);
  
  // wiki 鏈接: /wiki/xxx?sheet=yyy
  const wikiMatch = parsed.path.match(/\/wiki\/([A-Za-z0-9_-]+)/);
  if (wikiMatch) {
    const sheetMatch = inputUrl.match(/[?&]sheet=([A-Za-z0-9_]+)/);
    return { type: 'wiki', token: wikiMatch[1], sheetId: sheetMatch?.[1] };
  }
  
  // sheets 鏈接: /sheets/xxx?sheet=yyy
  const sheetsMatch = parsed.path.match(/\/sheets\/([A-Za-z0-9_-]+)/);
  if (sheetsMatch) {
    const sheetMatch = inputUrl.match(/[?&]sheet=([A-Za-z0-9_]+)/);
    return { type: 'sheets', token: sheetsMatch[1], sheetId: sheetMatch?.[1] };
  }
  
  return null;
}

// ===== 讀取飛書表格 =====
async function readSpreadsheet(spreadsheetToken, sheetId, range) {
  const token = await getTenantToken();
  
  // 先獲取 sheet 列表（如果沒指定 sheetId）
  if (!sheetId) {
    const meta = await httpRequest({
      hostname: 'open.feishu.cn',
      path: `/open-apis/sheets/v3/spreadsheets/${spreadsheetToken}/sheets/query`,
      method: 'GET',
      headers: { 'Authorization': `Bearer ${token}` },
    });
    
    if (meta.code !== 0) throw new Error(`獲取 sheet 列表失敗: ${meta.msg}`);
    const sheets = meta.data?.sheets || [];
    if (sheets.length === 0) throw new Error('表格中沒有 sheet');
    sheetId = sheets[0].sheet_id; // 默認讀第一個 sheet
  }
  
  // 讀取數據（使用 FormattedValue 獲取計算後的值）
  const readRange = range || `${sheetId}`;
  const data = await httpRequest({
    hostname: 'open.feishu.cn',
    path: `/open-apis/sheets/v2/spreadsheets/${spreadsheetToken}/values/${readRange}?valueRenderOption=FormattedValue`,
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` },
  });
  
  if (data.code !== 0) throw new Error(`讀取表格失敗: ${data.msg}`);
  
  return {
    sheetId,
    sheetName: data.data?.valueRange?.range || sheetId,
    values: data.data?.valueRange?.values || [],
  };
}

// ===== 處理請求 =====
async function handleRequest(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }
  
  // 健康檢查
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, time: new Date().toISOString() }));
    return;
  }
  
  // 讀取表格數據
  if (req.url.startsWith('/api/read') && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) body += chunk;
    
    try {
      const { feishuUrl, range } = JSON.parse(body);
      
      if (!feishuUrl) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: '請提供飛書鏈接' }));
        return;
      }
      
      const info = parseFeishuUrl(feishuUrl);
      if (!info) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: '無法識別飛書鏈接格式' }));
        return;
      }
      
      console.log(`📊 讀取: type=${info.type}, token=${info.token}, sheet=${info.sheetId || 'default'}`);
      
      const result = await readSpreadsheet(info.token, info.sheetId, range);
      
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, ...result }));
      
    } catch (e) {
      console.error('❌ 錯誤:', e.message);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }
  
  // 404
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
}

// ===== 啟動 =====
const server = http.createServer(handleRequest);
server.listen(PORT, '0.0.0.0', () => {
  console.log(`🦞 首銷日報代理服務器已啟動: http://localhost:${PORT}`);
  console.log(`   POST /api/read  — 讀取飛書表格數據`);
  console.log(`   GET  /health    — 健康檢查`);
});
