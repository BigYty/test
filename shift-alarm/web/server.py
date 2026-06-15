"""FastAPI Web 服务器"""

import os
import sys

# 将项目根目录添加到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from db.repository import Repository
from web.api_routes import create_router

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def create_app(repo: Repository | None = None) -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(title="排班闹钟", version="1.0.0")

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注入仓库层
    if repo is None:
        repo = Repository()
        repo.init_tables()
        repo.seed_defaults()

    # 注册 API 路由
    api_router = create_router(repo)
    app.include_router(api_router, prefix="/api")

    # 静态文件
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
