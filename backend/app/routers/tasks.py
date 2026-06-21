from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/", response_model=List[schemas.SyncTaskOut])
def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return crud.get_all_tasks(db, skip=skip, limit=limit)


@router.get("/{task_id}", response_model=schemas.SyncTaskDetail)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    logs = crud.get_task_logs(db, task_id, limit=1000)
    task_dict = schemas.SyncTaskOut.model_validate(task).model_dump()
    task_dict["logs"] = [schemas.SyncLogOut.model_validate(l) for l in logs]
    return schemas.SyncTaskDetail(**task_dict)


@router.get("/{task_id}/logs", response_model=List[schemas.SyncLogOut])
def list_task_logs(
    task_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return crud.get_task_logs(db, task_id, skip=skip, limit=limit)
