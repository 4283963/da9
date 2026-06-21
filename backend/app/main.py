from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app import models
from app.routers import repos, tasks, sync

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Git 仓库批量同步监视器",
    description="监控 cc1 ~ cc10 等 GitHub 仓库到备份服务器的批量同步状态",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos.router)
app.include_router(tasks.router)
app.include_router(sync.router)


@app.get("/")
def root():
    return {
        "name": "Git Sync Monitor API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
