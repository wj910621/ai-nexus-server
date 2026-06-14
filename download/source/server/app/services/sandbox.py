import docker, tempfile, os, time


def run_code(code: str, lang: str = 'python', timeout: int = 10) -> dict:
    ext = {'python': '.py', 'javascript': '.js'}.get(lang, '.py')
    img = {'python': 'python:3.11-slim', 'javascript': 'node:18-slim'}.get(lang, 'python:3.11-slim')
    cmd = {'python': ['python', '/code/code.py'], 'javascript': ['node', '/code/code.js']}.get(lang, ['python', '/code/code.py'])
    try:
        cli = docker.from_env()
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, f'code{ext}'), 'w') as f: f.write(code)
            c = cli.containers.run(img, cmd, volumes={td: {'bind': '/code', 'mode': 'ro'}}, mem_limit='256m', cpu_quota=50000, network_disabled=True, detach=True, remove=True)
            r = c.wait(timeout=timeout)
            return {'output': c.logs(stdout=True, stderr=True).decode(), 'exit_code': r['StatusCode'], 'error': ''}
    except Exception as e: return {'output': '', 'exit_code': 1, 'error': str(e)}
