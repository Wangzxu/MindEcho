# -*- coding: utf-8 -*-
import os
import uvicorn
from fastapi.responses import FileResponse, HTMLResponse
from app import create_app

app = create_app()

# 获取前端静态资源绝对路径
STATIC_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/public'))

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    """主页服务：渲染前端 index.html"""
    index_path = os.path.join(STATIC_FOLDER, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("MindEcho FastAPI Backend is running. Frontend static files not found.", status_code=200)


@app.get("/{path:path}")
def serve_static(path: str):
    """前端静态资源与 SPA (单页面应用) 路由兜底"""
    file_path = os.path.join(STATIC_FOLDER, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
        
    # 兜底：如果找不到该文件，可能是前端的路由链接，返回 index.html 供单页面托管
    index_path = os.path.join(STATIC_FOLDER, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("Resource not found", status_code=404)


if __name__ == '__main__':
    # 启动 Uvicorn 本地服务器，默认运行在 localhost:5000
    # 使用 "main:app" 代替 "app:app"，以避免与 app/ 目录命名冲突
    uvicorn.run("main:app", host='0.0.0.0', port=5000, reload=True)
