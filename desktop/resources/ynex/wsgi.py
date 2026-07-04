"""
Y·NEX AI WSGI 入口
用于 waitress / gunicorn 等生产级服务器启动

启动示例:
  waitress-serve --host 127.0.0.1 --port 7777 wsgi:app
  python -m waitress --host=127.0.0.1 --port=7777 wsgi:app

安全提示：默认监听 127.0.0.1，由 Nginx 反向代理处理外部访问。
如需局域网访问，请显式设置 YNEX_HOST=0.0.0.0 并配合防火墙。
"""
import os
from api_server import _create_flask_app

app = _create_flask_app()

if __name__ == "__main__":
    import waitress
    host = os.environ.get("YNEX_HOST", "127.0.0.1")
    port = int(os.environ.get("YNEX_PORT", "7777"))
    waitress.serve(app, host=host, port=port, threads=8)
