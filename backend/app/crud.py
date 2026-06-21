from sqlalchemy.orm import Session
from sqlalchemy import func, select
from typing import Optional, List
from app import models, schemas


def get_repo(db: Session, repo_id: int) -> Optional[models.Repo]:
    return db.query(models.Repo).filter(models.Repo.id == repo_id).first()


def get_repo_by_name(db: Session, name: str) -> Optional[models.Repo]:
    return db.query(models.Repo).filter(models.Repo.name == name).first()


def get_repos(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    active_only: Optional[bool] = None,
) -> List[models.Repo]:
    query = db.query(models.Repo)
    if active_only is not None:
        flag = 1 if active_only else 0
        query = query.filter(models.Repo.is_active == flag)
    return query.order_by(models.Repo.name.asc()).offset(skip).limit(limit).all()


def get_repos_with_stats(db: Session, active_only: Optional[bool] = None) -> List[dict]:
    repos = get_repos(db=db, active_only=active_only)
    result = []
    for repo in repos:
        total = (
            db.query(func.count(models.SyncTask.id))
            .filter(models.SyncTask.repo_id == repo.id)
            .scalar()
            or 0
        )
        success = (
            db.query(func.count(models.SyncTask.id))
            .filter(
                models.SyncTask.repo_id == repo.id,
                models.SyncTask.status == models.SyncStatus.SUCCESS,
            )
            .scalar()
            or 0
        )
        failed = (
            db.query(func.count(models.SyncTask.id))
            .filter(
                models.SyncTask.repo_id == repo.id,
                models.SyncTask.status == models.SyncStatus.FAILED,
            )
            .scalar()
            or 0
        )
        result.append(
            {
                "repo": repo,
                "total_tasks": total,
                "success_count": success,
                "failed_count": failed,
            }
        )
    return result


def create_repo(db: Session, repo: schemas.RepoCreate) -> models.Repo:
    db_repo = models.Repo(**repo.model_dump())
    db.add(db_repo)
    db.commit()
    db.refresh(db_repo)
    return db_repo


def create_repos_bulk(db: Session, repos_data: List[schemas.RepoCreate]) -> List[models.Repo]:
    created = []
    for repo in repos_data:
        existing = get_repo_by_name(db, repo.name)
        if existing:
            continue
        db_repo = models.Repo(**repo.model_dump())
        db.add(db_repo)
        created.append(db_repo)
    db.commit()
    for r in created:
        db.refresh(r)
    return created


def update_repo(db: Session, repo_id: int, updates: schemas.RepoUpdate) -> Optional[models.Repo]:
    db_repo = get_repo(db, repo_id)
    if not db_repo:
        return None
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_repo, key, value)
    db.commit()
    db.refresh(db_repo)
    return db_repo


def delete_repo(db: Session, repo_id: int) -> bool:
    db_repo = get_repo(db, repo_id)
    if not db_repo:
        return False
    db.delete(db_repo)
    db.commit()
    return True


def create_sync_task(db: Session, repo_id: int) -> models.SyncTask:
    task = models.SyncTask(
        repo_id=repo_id,
        status=models.SyncStatus.PENDING,
        progress=0,
        stage="",
        message="任务已创建，等待执行",
    )
    db.add(task)
    db.flush()
    repo = get_repo(db, repo_id)
    if repo:
        repo.latest_task_id = task.id
        db.flush()
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Optional[models.SyncTask]:
    return db.query(models.SyncTask).filter(models.SyncTask.id == task_id).first()


def get_repo_tasks(
    db: Session, repo_id: int, skip: int = 0, limit: int = 20
) -> List[models.SyncTask]:
    return (
        db.query(models.SyncTask)
        .filter(models.SyncTask.repo_id == repo_id)
        .order_by(models.SyncTask.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_all_tasks(
    db: Session, skip: int = 0, limit: int = 50
) -> List[models.SyncTask]:
    return (
        db.query(models.SyncTask)
        .order_by(models.SyncTask.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_task_status(
    db: Session,
    task_id: int,
    status: Optional[models.SyncStatus] = None,
    progress: Optional[int] = None,
    stage: Optional[str] = None,
    message: Optional[str] = None,
) -> Optional[models.SyncTask]:
    task = get_task(db, task_id)
    if not task:
        return None
    if status is not None:
        task.status = status
        if status in (models.SyncStatus.SUCCESS, models.SyncStatus.FAILED, models.SyncStatus.CANCELLED):
            from datetime import datetime, timezone
            if not task.finished_at:
                task.finished_at = datetime.now(timezone.utc)
            if task.started_at:
                task.duration_seconds = int((task.finished_at - task.started_at).total_seconds())
    if progress is not None:
        task.progress = max(0, min(100, progress))
    if stage is not None:
        task.stage = stage
    if message is not None:
        task.message = message
    db.commit()
    db.refresh(task)
    return task


def mark_task_started(db: Session, task_id: int) -> Optional[models.SyncTask]:
    from datetime import datetime, timezone
    task = get_task(db, task_id)
    if not task:
        return None
    task.started_at = datetime.now(timezone.utc)
    task.status = models.SyncStatus.CLONING
    task.progress = 5
    task.stage = "starting"
    task.message = "任务开始执行"
    db.commit()
    db.refresh(task)
    return task


def add_task_log(
    db: Session, task_id: int, message: str, level: str = "INFO"
) -> Optional[models.SyncLog]:
    task = get_task(db, task_id)
    if not task:
        return None
    log = models.SyncLog(task_id=task_id, level=level, message=message)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_task_logs(
    db: Session, task_id: int, skip: int = 0, limit: int = 500
) -> List[models.SyncLog]:
    return (
        db.query(models.SyncLog)
        .filter(models.SyncLog.task_id == task_id)
        .order_by(models.SyncLog.created_at.asc(), models.SyncLog.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
