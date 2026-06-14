from fastapi import APIRouter, Depends, HTTPException
from app.schemas.sandbox import CodeRunRequest, CodeRunResponse
from app.services.auth import get_current_user
import tempfile, os, time, json, docker

router = APIRouter()


@router.post('/sandbox/run', response_model=CodeRunResponse)
async def run_code(req: CodeRunRequest, user=Depends(get_current_user)):
    start = time.time()
    try:
        client = docker.from_env()
        ext = {'python': '.py', 'javascript': '.js'}.get(req.language, '.py')
        image = {'python': 'python:3.11-slim', 'javascript': 'node:18-slim'}.get(req.language, 'python:3.11-slim')
        cmd = {'python': ['python', '/code/code.py'], 'javascript': ['node', '/code/code.js']}.get(req.language, ['python', '/code/code.py'])

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, f'code{ext}'), 'w') as f:
                f.write(req.code)
            container = client.containers.run(
                image, cmd,
                volumes={tmpdir: {'bind': '/code', 'mode': 'ro'}},
                mem_limit='256m', cpu_quota=50000, network_disabled=True,
                detach=True, remove=True
            )
            result = container.wait(timeout=req.timeout)
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            return CodeRunResponse(output=logs, exit_code=result['StatusCode'], execution_time=round(time.time() - start, 2))
    except Exception as e:
        return CodeRunResponse(output='', error=str(e), exit_code=1, execution_time=round(time.time() - start, 2))
