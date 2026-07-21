from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.auth import get_current_user
import os
import stat

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.expanduser('~/.ynex-files'))
os.makedirs(BASE_DIR, exist_ok=True)


def _validate_path(path: str) -> str:
    full = os.path.abspath(os.path.join(BASE_DIR, path))
    if not full.startswith(BASE_DIR):
        raise HTTPException(403, '路径越权')
    if os.path.islink(full):
        real_path = os.path.realpath(full)
        if not real_path.startswith(BASE_DIR):
            raise HTTPException(403, '禁止访问符号链接')
    return full


@router.get('/files/list')
async def list_files(path: str = Query('.'), user=Depends(get_current_user)):
    full = _validate_path(path)
    if not os.path.exists(full):
        raise HTTPException(404, '路径不存在')
    if not os.path.isdir(full):
        raise HTTPException(400, '路径不是目录')
    items = []
    for e in os.scandir(full):
        if not e.name.startswith('.'):
            items.append({'name': e.name, 'type': 'directory' if e.is_dir() else 'file'})
    items.sort(key=lambda x: (x['type'] != 'directory', x['name']))
    return items


@router.get('/files/read')
async def read_file(path: str = Query('.'), user=Depends(get_current_user)):
    full = _validate_path(path)
    if not os.path.isfile(full):
        raise HTTPException(403, '无效文件路径')
    try:
        st = os.stat(full)
        if stat.S_ISLNK(st.st_mode):
            raise HTTPException(403, '禁止读取符号链接')
    except Exception:
        pass
    with open(full, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
        if len(content) > 1024 * 1024:
            raise HTTPException(413, '文件过大')
        return {'name': os.path.basename(full), 'content': content}


@router.post('/files/write')
async def write_file(path: str = Query('.'), content: str = '', user=Depends(get_current_user)):
    full = _validate_path(path)
    if len(content) > 1024 * 1024:
        raise HTTPException(413, '内容过大')
    try:
        parent = os.path.dirname(full)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
        return {'ok': True}
    except Exception as e:
        raise HTTPException(400, f'写入失败: {str(e)}')
