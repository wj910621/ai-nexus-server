from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.database import get_db
from app.models.document import Document
from app.schemas.knowledge import DocumentCreate, DocumentUpdate, DocumentResponse, SearchResult
from app.services.auth import get_current_user

router = APIRouter()


@router.get('/documents', response_model=list[DocumentResponse])
async def list_documents(category: str = '', user=Depends(get_current_user), db=Depends(get_db)):
    q = select(Document).where(Document.user_id == user.id)
    if category:
        q = q.where(Document.category == category)
    q = q.order_by(Document.updated_at.desc())
    r = await db.execute(q)
    return [DocumentResponse.model_validate(d) for d in r.scalars()]


@router.post('/documents', response_model=DocumentResponse)
async def create_document(req: DocumentCreate, user=Depends(get_current_user), db=Depends(get_db)):
    doc = Document(user_id=user.id, **req.model_dump())
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.get('/documents/{doc_id}', response_model=DocumentResponse)
async def get_document(doc_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404)
    return DocumentResponse.model_validate(doc)


@router.put('/documents/{doc_id}', response_model=DocumentResponse)
async def update_document(doc_id: int, req: DocumentUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404)
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(doc, k, v)
    await db.commit()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.delete('/documents/{doc_id}')
async def delete_document(doc_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404)
    await db.delete(doc)
    await db.commit()
    return {'ok': True}


@router.get('/documents/search', response_model=list[SearchResult])
async def search_documents(q: str = Query('', min_length=1), user=Depends(get_current_user), db=Depends(get_db)):
    query = select(Document).where(
        Document.user_id == user.id,
        or_(Document.title.ilike(f'%{q}%'), Document.content.ilike(f'%{q}%'))
    ).order_by(Document.updated_at.desc())
    r = await db.execute(query)
    return [SearchResult(id=d.id, title=d.title, content=d.content[:120], score=1.0) for d in r.scalars()]

import os, tempfile, json


@router.post('/knowledge/rag')
async def rag_search(q: str = Query(...), limit: int = Query(5), user=Depends(get_current_user), db=Depends(get_db)):
    """Search knowledge base for RAG context (server-side)"""
    from app.models.document import Document
    from sqlalchemy import select, or_
    
    query = select(Document).where(
        Document.user_id == user.id,
        or_(Document.title.ilike(f'%{q}%'), Document.content.ilike(f'%{q}%'))
    ).order_by(Document.updated_at.desc()).limit(limit)
    r = await db.execute(query)
    docs = r.scalars().all()
    
    results = []
    for d in docs:
        results.append({
            'id': d.id,
            'title': d.title,
            'content': d.content[:500],
            'score': 1.0
        })
    return results


@router.post('/knowledge/upload')
async def upload_document(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Upload a file and save as knowledge document"""
    from app.models.document import Document
    
    content = ''
    filename = file.filename or 'untitled'
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    # Read file content
    try:
        raw = await file.read()
        if ext in ('txt', 'md', 'py', 'js', 'ts', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'java', 'go', 'rs', 'cpp', 'c', 'h', 'csv'):
            content = raw.decode('utf-8', errors='replace')
        else:
            # Binary or unsupported - store as text
            content = raw.decode('utf-8', errors='replace')
    except Exception as e:
        raise HTTPException(400, f'Failed to read file: {str(e)}')
    
    if not content.strip():
        raise HTTPException(400, 'Empty file content')
    
    # Determine category
    cat = 'other'
    code_exts = {'py': 'code', 'js': 'code', 'ts': 'code', 'java': 'code', 'go': 'code', 'rs': 'code', 'cpp': 'code', 'c': 'code', 'h': 'code'}
    if ext in code_exts:
        cat = code_exts[ext]
    elif ext == 'md':
        cat = 'guide'
    elif ext == 'txt':
        cat = 'reference'
    
    # Save to DB
    doc = Document(
        user_id=user.id,
        title=filename,
        content=content,
        category=cat
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    return {'id': doc.id, 'title': doc.title, 'category': doc.category, 'size': len(content)}


