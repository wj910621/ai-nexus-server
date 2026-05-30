@echo off
chcp 65001 >nul
echo ============================================
echo  AI Nexus 阿里云一键部署脚本
echo ============================================
echo.

set SERVER_IP=120.79.17.184
set SERVER_USER=admin
set REMOTE_DIR=/home/admin/ai-nexus

echo [1/4] 打包项目文件...
powershell -Command "Compress-Archive -Path 'G:\大模型聚合网站\index.html','G:\大模型聚合网站\server\server.js' -DestinationPath '%TEMP%\ai-nexus-deploy.zip' -Force"
if errorlevel 1 (
    echo 打包失败！请确认以下文件存在：
    echo   G:\大模型聚合网站\index.html
    echo   G:\大模型聚合网站\server\server.js
    pause
    exit /b 1
)
echo 打包完成: %TEMP%\ai-nexus-deploy.zip

echo.
echo [2/4] 上传文件到服务器 %SERVER_IP% ...
echo 请输入服务器密码：
scp %TEMP%\ai-nexus-deploy.zip %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
if errorlevel 1 (
    echo 上传失败！请检查网络和密码
    pause
    exit /b 1
)

echo.
echo [3/4] 服务器上解压并安装依赖...
ssh %SERVER_USER%@%SERVER_IP% "cd %REMOTE_DIR% && unzip -o ai-nexus-deploy.zip && npm install express cors dotenv 2>/dev/null; echo '依赖安装完成'"

echo.
echo [4/4] 启动服务...
ssh %SERVER_USER%@%SERVER_IP% "cd %REMOTE_DIR% && nohup node server.js > /tmp/ai-nexus.log 2>&1 & sleep 2 && curl -s http://localhost:3001/api/status && echo '' && echo '=== 服务已启动 ===' && echo '测试地址: http://%SERVER_IP%:3001'"

echo.
echo ============================================
echo  部署完成！
echo  网站地址: http://%SERVER_IP%:3001
echo ============================================
echo.
echo 下一步：配置阿里云安全组，开放 3001 端口
echo   阿里云控制台 → 轻量服务器 → 防火墙 → 添加规则
echo   端口：3001  协议：TCP  授权：0.0.0.0/0
echo.
pause
