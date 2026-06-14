from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.auth import get_current_user
import os

router = APIRouter()
BASE_DIR = os.path.expanduser('~')


@router.get('/files/list')
async def list_files(path: str = Query('.'), user=Depends(get_current_user)):
    full = os.path.abspath(os.path.join(BASE_DIR, path))
    if not full.startswith(BASE_DIR):
        raise HTTPException(403)
    if not os.path.exists(full):
        raise HTTPException(404)
    items = []
    for e in os.scandir(full):
        if not e.name.startswith('.'):
            items.append({'name': e.name, 'type': 'directory' if e.is_dir() else 'file'})
    items.sort(key=lambda x: (x['type'] != 'directory', x['name']))
    return items


@router.get('/files/read')
async def read_file(path: str = Query('.'), user=Depends(get_current_user)):
    full = os.path.abspath(os.path.join(BASE_DIR, path))
    if not full.startswith(BASE_DIR) or not os.path.isfile(full):
        raise HTTPException(403)
    with open(full, 'r', encoding='utf-8', errors='replace') as f:
        return {'name': os.path.basename(full), 'content': f.read()}


@router.post('/files/write')
async def write_file(path: str = Query('.'), content: str = '', user=Depends(get_current_user)):
    full = os.path.abspath(os.path.join(BASE_DIR, path))
    if not full.startswith(BASE_DIR):
        raise HTTPException(403)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(content)
    return {'ok': True}
