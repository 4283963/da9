from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    CLONING = "cloning"
    PUSHING = "pushing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Repo(Base):
    __tablename__ = "repos"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    source_url = Column(String(512), nullable=False)
    target_url = Column(String(512), nullable=False)
    description = Column(String(512), default="")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tasks = relationship("SyncTask", back_populates="repo", cascade="all, delete-orphan", foreign_keys="SyncTask.repo_id")
    latest_task_id = Column(Integer, ForeignKey("sync_tasks.id"), nullable=True)
    latest_task = relationship("SyncTask", foreign_keys=[latest_task_id], post_update=True)


class SyncTask(Base):
    __tablename__ = "sync_tasks"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repos.id"), nullable=False)
    status = Column(SAEnum(SyncStatus), default=SyncStatus.PENDING, nullable=False, index=True)
    progress = Column(Integer, default=0)
    stage = Column(String(64), default="")
    message = Column(Text, default="")
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    repo = relationship("Repo", foreign_keys=[repo_id], back_populates="tasks")
    logs = relationship("SyncLog", back_populates="task", cascade="all, delete-orphan")


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("sync_tasks.id"), nullable=False, index=True)
    level = Column(String(16), default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("SyncTask", back_populates="logs")
