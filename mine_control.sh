#!/bin/bash
# ==============================================
# MineSttr 自动控制脚本 (GitHub Actions 版)
# ==============================================

# 配置信息通过 GitHub Secrets 注入
API_KEY="${API_KEY}"
SERVER_ID="${SERVER_ID}"
ACTION="${ACTION}"
PROXY="${PROXY}"

API_URL="https://mine.sttr.io/server/${SERVER_ID}/poweraction"
USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"

echo "==================================================="
echo "🚀 MineSttr 服务器控制脚本"
echo "==================================================="
echo "⏰ 执行时间: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "🎯 操作类型: $ACTION"
echo "🖥️ 服务器ID: $SERVER_ID"
echo "==================================================="

# 发送 API 请求
echo ""
echo "📡 正在发送请求（通过代理）..."
echo "🌐 代理地址: $PROXY"

RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT "$API_URL" \
  --proxy "$PROXY" \
  -H "Accept: application/json" \
  -H "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Origin: https://minestrator.com" \
  -H "Referer: https://minestrator.com/" \
  -H "Sec-Fetch-Dest: empty" \
  -H "Sec-Fetch-Mode: cors" \
  -H "Sec-Fetch-Site: cross-site" \
  -H "User-Agent: $USER_AGENT" \
  --data-raw "{\"poweraction\": \"$ACTION\"}")

# 分离响应体和状态码
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "📊 HTTP 状态码: $HTTP_CODE"

# 根据状态码处理结果
case $HTTP_CODE in
  200)
    echo "✅ 操作成功 → $ACTION"
    if [ -n "$BODY" ]; then
      echo "📄 响应内容:"
      echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
    fi
    exit 0
    ;;
  400)
    echo "⚠️ 请求无效 (HTTP 400)"
    [ -n "$BODY" ] && echo "📄 错误详情: $BODY"
    exit 1
    ;;
  403)
    echo "❌ 权限不足 (HTTP 403)"
    exit 1
    ;;
  404)
    echo "❌ 找不到服务器 (HTTP 404)"
    exit 1
    ;;
  419)
    echo "⚠️ Token 过期或无效 (HTTP 419)"
    exit 1
    ;;
  *)
    echo "⚠️ 未知错误"
    echo "状态码: $HTTP_CODE"
    [ -n "$BODY" ] && echo "📄 响应内容: $BODY"
    exit 1
    ;;
esac
