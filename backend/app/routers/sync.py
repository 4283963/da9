from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app import crud, schemas, models
from app.sync_executor import sync_manager

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _build_source_url(name: str) -> str:
    return f"https://github.com/cc-demo/{name}.git"


def _build_target_url(name: str, prefix: str) -> str:
    return f"{prefix}/{name}.git"


@router.post("/start", response_model=schemas.SyncResponse)
def start_sync(
    req: schemas.SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    from app.config import settings

    repos: List[models.Repo] = []
    if req.all_active:
        repos = crud.get_repos(db, active_only=True)
    elif req.repo_ids:
        for rid in req.repo_ids:
            r = crud.get_repo(db, rid)
            if r and r.is_active:
                repos.append(r)
    else:
        raise HTTPException(
            status_code=400,
            detail="请指定 repo_ids 或设置 all_active=true",
        )

    if not repos:
        return schemas.SyncResponse(message="没有可同步的仓库", started_tasks=0, task_ids=[])

    task_ids = []
    pending_items = []
    for repo in repos:
        task = crud.create_sync_task(db, repo.id)
        task_ids.append(task.id)
        pending_items.append((task.id, repo.id))

    sync_manager.submit_tasks(pending_items)

    return schemas.SyncResponse(
        message=f"已发起 {len(pending_items)} 个同步任务",
        started_tasks=len(pending_items),
        task_ids=task_ids,
    )


@router.post("/start/{repo_id}", response_model=schemas.SyncResponse)
def start_single_sync(
    repo_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    repo = crud.get_repo(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if not repo.is_active:
        raise HTTPException(status_code=400, detail="仓库未启用")

    task = crud.create_sync_task(db, repo.id)
    sync_manager.submit_task(task.id, repo.id)

    return schemas.SyncResponse(
        message=f"已发起仓库 {repo.name} 的同步任务",
        started_tasks=1,
        task_ids=[task.id],
    )


@router.get("/status")
def get_sync_status():
    return {
        "running_count": sync_manager.get_running_count(),
        "queued_count": sync_manager.get_queue_size(),
        "max_workers": sync_manager.max_workers,
    }
