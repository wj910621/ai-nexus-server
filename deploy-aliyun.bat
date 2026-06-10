@echo off
chcp 65001 >nul
echo ============================================
echo  Nexus Hub 阿里云一键部署脚本（更新版）
echo ============================================
echo.

set SERVER_IP=120.79.17.184
set SERVER_USER=admin
set REMOTE_DIR=/home/admin/ai-nexus

echo [1/5] 本地检查文件...
if not exist "G:\大模型聚合网站\server.js" (
    echo 错误：找不到 G:\大模型聚合网站\server.js
    pause
    exit /b 1
)
if not exist "G:\大模型聚合网站\package.json" (
    echo 错误：找不到 package.json
    pause
    exit /b 1
)
echo     server.js  ✓
echo     package.json  ✓
echo     dashboard.html  ✓
echo     landing.html  ✓
echo     index.html  ✓
echo     icons/  ✓
echo     products/  ✓

echo.
echo [2/5] 打包项目文件...
powershell -Command "& {
    $items = @(
        'G:\大模型聚合网站\server.js',
        'G:\大模型聚合网站\package.json',
        'G:\大模型聚合网站\dashboard.html',
        'G:\大模型聚合网站\landing.html',
        'G:\大模型聚合网站\index.html',
        'G:\大模型聚合网站\sw.js',
        'G:\大模型聚合网站\manifest.json',
        'G:\大模型聚合网站\check_live.js',
        'G:\大模型聚合网站\railway.json',
        'G:\大模型聚合网站\render.yaml',
        'G:\大模型聚合网站\.env.example',
        'G:\大模型聚合网站\products',
        'G:\大模型聚合网站\icons'
    ) | Where-Object { Test-Path $_ }
    if ($items.Count -eq 0) { exit 1 }
    Compress-Archive -Path $items -DestinationPath '%TEMP%\nexus-hub-deploy.zip' -Force
    Write-Host ('打包完成：' + (Get-Item '%TEMP%\nexus-hub-deploy.zip').Length / 1KB + ' KB')
}"
if errorlevel 1 (
    echo 打包失败
    pause
    exit /b 1
)

echo.
echo [3/5] 上传文件到服务器 %SERVER_IP% ...
echo 请输入服务器密码（输入时不会显示）：
scp "%TEMP%\nexus-hub-deploy.zip" %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
if errorlevel 1 (
    echo 上传失败！请检查：
    echo   1. 服务器 IP 是否正确（%SERVER_IP%）
    echo   2. 密码是否正确
    echo   3. 安全组是否开放了 22 端口（SSH）
    pause
    exit /b 1
)
echo 上传成功

echo.
echo [4/5] 服务器上解压 + 安装依赖...
ssh %SERVER_USER%@%SERVER_IP% "cd %REMOTE_DIR% && unzip -o nexus-hub-deploy.zip && npm install --production 2>&1 && echo '=== 依赖安装完成 ==='"
if errorlevel 1 (
    echo 解压或安装依赖失败
    pause
    exit /b 1
)

echo.
echo [5/5] 启动/重启服务...
ssh %SERVER_USER%@%SERVER_IP% "cd %REMOTE_DIR% && pgrep -f 'node server.js' && pkill -f 'node server.js' && echo '已停止旧进程' || echo '无旧进程'; sleep 1; nohup node server.js > /tmp/nexus-hub.log 2>&1 & sleep 2; echo '服务启动完成'; curl -s http://localhost:3001/api/status"

echo.
echo ============================================
echo  部署完成！
echo  访问地址: http://%SERVER_IP%:3001
echo ============================================
echo.
echo 常用远程命令：
echo   查看日志:     ssh %SERVER_USER%@%SERVER_IP% "tail -f /tmp/nexus-hub.log"
echo   查看状态:     curl http://%SERVER_IP%:3001/api/status
echo   手动重启:     ssh %SERVER_USER%@%SERVER_IP% "pkill -f 'node server.js'; nohup node /home/admin/ai-nexus/server.js > /tmp/nexus-hub.log 2>&1 &"
echo   更新 .env:    ssh %SERVER_USER%@%SERVER_IP% "nano /home/admin/ai-nexus/.env"
echo.
echo 下一步：配置阿里云防火墙
echo   阿里云控制台 → 轻量应用服务器 → 防火墙 → 添加规则
echo   端口: 3001  协议: TCP  授权对象: 0.0.0.0/0
echo.
echo 如果没有域名转发（Nginx），可跳过。
echo 需要域名转发：ssh admin@120.79.17.184 "sudo apt install nginx -y && sudo systemctl start nginx"
echo.
pause
