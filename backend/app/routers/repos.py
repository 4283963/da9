from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app import crud, schemas, models

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.get("/", response_model=List[schemas.RepoWithStats])
def list_repos(
    active_only: Optional[bool] = Query(None, description="只返回启用的仓库"),
    db: Session = Depends(get_db),
):
    items = crud.get_repos_with_stats(db, active_only=active_only)
    out = []
    for item in items:
        repo = item["repo"]
        data = schemas.RepoOut.model_validate(repo).model_dump()
        data.update(
            {
                "total_tasks": item["total_tasks"],
                "success_count": item["success_count"],
                "failed_count": item["failed_count"],
            }
        )
        out.append(schemas.RepoWithStats(**data))
    return out


@router.get("/{repo_id}", response_model=schemas.RepoWithStats)
def get_repo(repo_id: int, db: Session = Depends(get_db)):
    repo = crud.get_repo(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    items = crud.get_repos_with_stats(db, active_only=None)
    for item in items:
        if item["repo"].id == repo_id:
            data = schemas.RepoOut.model_validate(repo).model_dump()
            data.update(
                {
                    "total_tasks": item["total_tasks"],
                    "success_count": item["success_count"],
                    "failed_count": item["failed_count"],
                }
            )
            return schemas.RepoWithStats(**data)
    data = schemas.RepoOut.model_validate(repo).model_dump()
    data.update({"total_tasks": 0, "success_count": 0, "failed_count": 0})
    return schemas.RepoWithStats(**data)


@router.post("/", response_model=schemas.RepoOut, status_code=201)
def create_repo(repo: schemas.RepoCreate, db: Session = Depends(get_db)):
    existing = crud.get_repo_by_name(db, repo.name)
    if existing:
        raise HTTPException(status_code=400, detail="同名仓库已存在")
    return crud.create_repo(db, repo)


@router.post("/bulk", response_model=List[schemas.RepoOut])
def bulk_create_repos(repos: List[schemas.RepoCreate], db: Session = Depends(get_db)):
    return crud.create_repos_bulk(db, repos)


@router.patch("/{repo_id}", response_model=schemas.RepoOut)
def update_repo(repo_id: int, updates: schemas.RepoUpdate, db: Session = Depends(get_db)):
    repo = crud.update_repo(db, repo_id, updates)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return repo


@router.delete("/{repo_id}")
def delete_repo(repo_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_repo(db, repo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return {"message": "删除成功"}


@router.get("/{repo_id}/tasks", response_model=List[schemas.SyncTaskOut])
def list_repo_tasks(
    repo_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    repo = crud.get_repo(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return crud.get_repo_tasks(db, repo_id, skip=skip, limit=limit)
