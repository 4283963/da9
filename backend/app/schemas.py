from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.models import SyncStatus


class RepoBase(BaseModel):
    name: str
    source_url: str
    target_url: str
    description: Optional[str] = ""
    is_active: Optional[int] = 1


class RepoCreate(RepoBase):
    pass


class RepoUpdate(BaseModel):
    name: Optional[str] = None
    source_url: Optional[str] = None
    target_url: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


class SyncTaskBase(BaseModel):
    status: SyncStatus
    progress: Optional[int] = 0
    stage: Optional[str] = ""
    message: Optional[str] = ""


class SyncTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_id: int
    status: SyncStatus
    progress: int
    stage: str
    message: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: int
    created_at: datetime


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_url: str
    target_url: str
    description: str
    is_active: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    latest_task: Optional[SyncTaskOut] = None


class RepoWithStats(RepoOut):
    total_tasks: int = 0
    success_count: int = 0
    failed_count: int = 0


class SyncLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    level: str
    message: str
    created_at: datetime


class SyncTaskDetail(SyncTaskOut):
    logs: List[SyncLogOut] = []


class SyncRequest(BaseModel):
    repo_ids: Optional[List[int]] = None
    all_active: Optional[bool] = False


class SyncResponse(BaseModel):
    message: str
    started_tasks: int
    task_ids: List[int] = []
