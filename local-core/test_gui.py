"""
GUI 界面导入与资源检查测试
"""
import sys
sys.path.insert(0, r'c:\Y·NEX版Y·NEX项目')

from pathlib import Path
from gui.particle_window import ParticleFaceWindow, launch_gui, _resource_path

print('Testing GUI module imports...')
print('OK particle_window')

html_path = _resource_path('gui/particle_face.html')
print(f'OK resource_path: {html_path}')

p = Path(html_path)
print(f'OK HTML exists: {p.exists()}, size: {p.stat().st_size if p.exists() else 0}')

p2 = Path(_resource_path('gui/qwebchannel.js'))
print(f'OK qwebchannel.js exists: {p2.exists()}, size: {p2.stat().st_size if p2.exists() else 0}')

# 检查 HTML 包含 Three.js CDN 引用
html_content = p.read_text(encoding='utf-8')
print(f'OK HTML has Three.js: {"three.min.js" in html_content}')
print(f'OK HTML has shape buttons: {"changeShape" in html_content}')
print(f'OK HTML has control buttons: {"quickAction" in html_content}')

print('\nPASS GUI module import check')
