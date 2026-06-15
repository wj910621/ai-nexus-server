"""上传 TriGenClaw 桌面端安装包到服务器"""
import paramiko
import os
import time

HOST = '120.79.17.184'
USER = 'admin'
PASS = 'Wangjie910621'
PORT = 22

local_file = r'G:\大模型聚合网站\download\trigenclaw-build\release\TriGenClaw-1.0.0-win-Setup.exe'
remote_dir = '/home/admin/ai-nexus/download'

print(f'安装包: {local_file}')
print(f'大小: {os.path.getsize(local_file) / 1024 / 1024:.1f} MB')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, look_for_keys=False, allow_agent=False, timeout=30)
    print(f'已连接到 {HOST}')
    
    # 创建远程目录
    _, stdout, stderr = ssh.exec_command(f'mkdir -p {remote_dir}')
    stdout.channel.recv_exit_status()
    
    # 上传文件
    sftp = ssh.open_sftp()
    remote_file = f'{remote_dir}/TriGenClaw-1.0.0-win-Setup.exe'
    
    # 使用 paramiko 的 put 方法
    def progress_callback(transferred, total):
        pct = transferred / total * 100
        print(f'\r上传进度: {pct:.1f}% ({transferred/1024/1024:.1f}MB)', end='')
    
    sftp.put(local_file, remote_file, callback=progress_callback)
    print(f'\n上传完成: {remote_file}')
    sftp.close()
    
    # 设置权限
    ssh.exec_command(f'chmod 644 {remote_file}')
    
    # 检查下载目录
    _, stdout, _ = ssh.exec_command(f'ls -la {remote_dir}/')
    print(f'\n下载目录:\n{stdout.read().decode()}')
    
    # 检查现有的下载链接
    _, stdout, _ = ssh.exec_command(f'grep -n "download" /home/admin/ai-nexus/index.html 2>/dev/null | head -20')
    print(f'当前下载链接:\n{stdout.read().decode()}')
    
    print('\n✅ 上传完成!')
    
except paramiko.AuthenticationException:
    print(f'认证失败 - 密码可能已更改')
    # 尝试其他密码或方法
except Exception as e:
    print(f'错误: {e}')
finally:
    ssh.close()
