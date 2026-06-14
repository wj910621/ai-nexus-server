from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx, json
from app.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.chat import ConversationCreate, ConversationResponse, MessageResponse
from app.services.auth import get_current_user
from app.config import settings

router = APIRouter()


@router.get('/conversations', response_model=list[ConversationResponse])
async def list_convs(user=Depends(get_current_user), db=Depends(get_db)):
    r = await db.execute(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()))
    return [ConversationResponse.model_validate(c) for c in r.scalars()]


@router.post('/conversations', response_model=ConversationResponse)
async def create_conv(req: ConversationCreate, user=Depends(get_current_user), db=Depends(get_db)):
    c = Conversation(user_id=user.id, **req.model_dump())
    db.add(c); await db.commit(); await db.refresh(c)
    return ConversationResponse.model_validate(c)


@router.get('/conversations/{cid}', response_model=ConversationResponse)
async def get_conv(cid: int, user=Depends(get_current_user), db=Depends(get_db)):
    c = await db.get(Conversation, cid)
    if not c or c.user_id != user.id: raise HTTPException(404)
    return ConversationResponse.model_validate(c)


@router.delete('/conversations/{cid}')
async def delete_conv(cid: int, user=Depends(get_current_user), db=Depends(get_db)):
    c = await db.get(Conversation, cid)
    if not c or c.user_id != user.id: raise HTTPException(404)
    await db.delete(c); await db.commit()
    return {'ok': True}


@router.get('/conversations/{cid}/messages', response_model=list[MessageResponse])
async def get_msgs(cid: int, user=Depends(get_current_user), db=Depends(get_db)):
    c = await db.get(Conversation, cid)
    if not c or c.user_id != user.id: raise HTTPException(404)
    r = await db.execute(select(Message).where(Message.conversation_id == cid).order_by(Message.timestamp))
    return [MessageResponse.model_validate(m) for m in r.scalars()]


@router.post('/chat/stream')
async def chat_stream(
    cid: int, msg: str, model: str = 'deepseek-chat',
    temp: float = 0.7, mt: int = 4096, sysp: str = '',
    user=Depends(get_current_user), db=Depends(get_db)
):
    conv = await db.get(Conversation, cid)
    if not conv or conv.user_id != user.id: raise HTTPException(404)

    db.add(Message(conversation_id=conv.id, role='user', content=msg))
    await db.commit()

    msgs = []
    sp = sysp or conv.system_prompt
    if sp: msgs.append({'role': 'system', 'content': sp})
    r = await db.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.timestamp))
    for m in r.scalars(): msgs.append({'role': m.role, 'content': m.content})

    async def gen():
        full = ''
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream('POST', f'{settings.api_base_url}/api/chat', json={
                'model': model, 'messages': msgs, 'temperature': temp, 'max_tokens': mt, 'stream': True
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith('data: ') and line.strip() != 'data: [DONE]':
                        try:
                            d = json.loads(line[6:])
                            c = d.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if c:
                                full += c
                                yield f'data: {json.dumps({"c": c})}\n\n'
                        except: pass
        db.add(Message(conversation_id=conv.id, role='assistant', content=full or '(no response)'))
        await db.commit()
        yield f'data: {json.dumps({"done": True})}\n\n'

    return StreamingResponse(gen(), media_type='text/event-stream')
