#!/bin/bash

# 接收从 YML 传过来的变量
PROXY="http://127.0.0.1:8080"
API_URL="https://mine.sttr.io/server/${SERVER_ID}/poweraction"

echo "🔧 Minestrator 日常任务"
echo "========================================"
echo "🕐 运行时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "🖥️ 服务器: MineStrator-FR 🇫🇷"
echo ""

# 🛡️ 核心修复：自动检测并补全 Bearer 前缀
# 防止因为 GitHub Secrets 里漏填了 Bearer 而导致 403 报错
if [[ "$MINESTRATOR_APIKEY" != Bearer* ]]; then
  echo "🔍 格式检测: API Key 缺少 Bearer 前缀，已自动为您补全。"
  FINAL_AUTH="Bearer $MINESTRATOR_APIKEY"
else
  echo "🔍 格式检测: API Key 格式正确。"
  FINAL_AUTH="$MINESTRATOR_APIKEY"
fi

echo "========================================"
echo "🚀 正在发送重启请求..."

# 发送 API 请求 (使用自动纠错后的 FINAL_AUTH)
RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT "$API_URL" \
  --proxy "$PROXY" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -H "Authorization: $FINAL_AUTH" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  --data-raw '{"poweraction": "restart"}')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "   响应码: $HTTP_CODE"
echo "   响应体: $BODY"
echo ""
echo "========================================"

# 判断返回状态码是否为 200 (成功)
if [ "$HTTP_CODE" -eq 200 ]; then
  echo "✅ 服务器重启成功！"
  
  # TG 推送逻辑
  if [ -n "$TG_BOT" ]; then
    CHAT_ID=$(echo "$TG_BOT" | cut -d',' -f1)
    TOKEN=$(echo "$TG_BOT" | cut -d',' -f2)
    MSG="🎮 Minestrator 重启成功！%0A🕐 运行时间: $(date '+%Y-%m-%d %H:%M:%S')%0A🖥 服务器: MineStrator-FR"
    curl -s -x "$PROXY" "https://api.telegram.org/bot${TOKEN}/sendMessage?chat_id=${CHAT_ID}&text=${MSG}" > /dev/null
    echo "📨 TG 推送成功"
  fi
else
  echo "❌ 服务器重启失败！请检查 Server ID 或 API Key 是否过期。"
  exit 1
fi

echo "========================================"
echo "🎉 任务完成！"
