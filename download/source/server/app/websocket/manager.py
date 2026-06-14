from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

router = APIRouter()

class ConnMgr:
    def __init__(self): self.active = {}
    async def connect(self, cid, ws):
        await ws.accept()
        self.active.setdefault(cid, []).append(ws)
    def disconnect(self, cid, ws):
        if cid in self.active:
            self.active[cid] = [w for w in self.active[cid] if w != ws]
            if not self.active[cid]: del self.active[cid]
    async def broadcast(self, cid, msg):
        for ws in self.active.get(cid, []):
            try: await ws.send_text(msg)
            except: pass

mgr = ConnMgr()

@router.websocket('/chat/{conv_id}')
async def ws_ep(ws: WebSocket, conv_id: int):
    await mgr.connect(conv_id, ws)
    try:
        while True:
            d = json.loads(await ws.receive_text())
            if d.get('type') == 'ping':
                await ws.send_text(json.dumps({'type': 'pong'}))
    except WebSocketDisconnect:
        mgr.disconnect(conv_id, ws)
