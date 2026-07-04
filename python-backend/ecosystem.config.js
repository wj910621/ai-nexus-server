module.exports = {
  apps: [{
    name: 'nexus-python',
    script: 'venv/bin/uvicorn',
    args: 'app.main:app --host 0.0.0.0 --port 8000 --reload',
    cwd: '/home/admin/ai-nexus/python-backend',
    env: {
      PYTHONPATH: '/home/admin/ai-nexus/python-backend',
      DATABASE_URL: 'sqlite+aiosqlite:///./nexus.db'
    },
    max_restarts: 10,
    restart_delay: 3000
  }]
};
