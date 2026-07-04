#!/bin/bash
cd /home/admin/ai-nexus/python-backend
export PYTHONPATH="/home/admin/ai-nexus/python-backend"
export DATABASE_URL="sqlite+aiosqlite:///./nexus.db"
exec /home/admin/ai-nexus/python-backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
