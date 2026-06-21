#!/bin/bash
# ============================================================
# Nginx manifest.json 修复脚本
# 用法：在服务器终端执行 bash fix-nginx-manifest.sh
# ============================================================

echo "🔧 Nginx manifest.json 修复脚本"
echo "=================================="

# 1. 找到 Nginx 配置文件
NGINX_CONF="/etc/nginx/conf.d/nexus-studio.conf"
if [ ! -f "$NGINX_CONF" ]; then
    NGINX_CONF="/etc/nginx/conf.d/default.conf"
fi
if [ ! -f "$NGINX_CONF" ]; then
    NGINX_CONF="/etc/nginx/nginx.conf"
fi

# 如果没找到，尝试搜索
if [ ! -f "$NGINX_CONF" ]; then
    echo "🔍 搜索 Nginx 站点配置..."
    NGINX_CONF=$(grep -rl "j3trisheng.com\|nexus-studio\|/home/admin/nexus" /etc/nginx/conf.d/ 2>/dev/null | head -1)
    if [ -z "$NGINX_CONF" ]; then
        echo "❌ 未找到 Nginx 配置文件，请手动检查 /etc/nginx/ 目录"
        exit 1
    fi
fi

echo "📄 找到配置文件: $NGINX_CONF"

# 2. 检查是否已有 manifest.json 规则
if grep -q "location.*manifest.json" "$NGINX_CONF"; then
    echo "✅ manifest.json 规则已存在，无需修改"
else
    echo "📝 添加 manifest.json 例外规则..."
    
    # 创建临时文件，在第一个 location / 之前插入 manifest 规则
    TEMP_FILE=$(mktemp)
    
    # 读取原文件并在适当位置插入新规则
    awk '
    BEGIN { inserted=0 }
    /^[[:space:]]*location[[:space:]]+\/[^m]/ && !inserted {
        print "    # Manifest JSON 直接返回，不经过 SPA fallback"
        print "    location = /manifest.json {"
        print "        try_files $uri =404;"
        print "    }"
        print ""
        inserted=1
    }
    { print }
    ' "$NGINX_CONF" > "$TEMP_FILE"
    
    # 如果没有找到 location /，就在 server 块内最后添加
    if ! grep -q "location = /manifest.json" "$TEMP_FILE"; then
        echo "⚠️  未找到标准 location，尝试追加到文件末尾..."
        # 在最后一个 } 之前添加
        sed -i '/^}$/i\    # Manifest JSON 直接返回，不经过 SPA fallback\n    location = /manifest.json {\n        try_files $uri =404;\n    }\n' "$NGINX_CONF"
    else
        mv "$TEMP_FILE" "$NGINX_CONF"
    fi
    
    rm -f "$TEMP_FILE"
    echo "✅ 规则已添加"
fi

# 3. 测试 Nginx 配置
echo ""
echo "🧪 测试 Nginx 配置..."
if nginx -t; then
    echo "✅ 配置测试通过"
    
    # 4. 重载 Nginx
    echo ""
    echo "🔄 重载 Nginx..."
    if systemctl reload nginx 2>/dev/null || service nginx reload 2>/dev/null || nginx -s reload 2>/dev/null; then
        echo "✅ Nginx 重载成功"
    else
        echo "⚠️  重载失败，尝试重启..."
        systemctl restart nginx || service nginx restart
    fi
else
    echo "❌ 配置测试失败，请检查 $NGINX_CONF"
    exit 1
fi

# 5. 验证修复
echo ""
echo "🔍 验证 manifest.json 访问..."
sleep 1
if curl -s http://localhost/manifest.json | head -1 | grep -q "^{"; then
    echo "✅ manifest.json 现在可以正常访问了！"
else
    echo "⚠️  验证未完成，请手动测试: curl http://localhost/manifest.json"
fi

echo ""
echo "🎉 修复完成！"
