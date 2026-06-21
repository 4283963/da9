import subprocess
import os
import shutil
import threading
import queue
import logging
import time
from typing import Optional, List, Dict, Tuple
from app.database import SessionLocal
from app import crud, models
from app.config import settings

logger = logging.getLogger(__name__)

_thread_local = threading.local()


def get_thread_db():
    if not hasattr(_thread_local, "db") or _thread_local.db is None:
        _thread_local.db = SessionLocal()
    return _thread_local.db


def close_thread_db():
    if hasattr(_thread_local, "db") and _thread_local.db is not None:
        try:
            _thread_local.db.close()
        except Exception:
            pass
        _thread_local.db = None


class LogBuffer:
    def __init__(self, task_id: int, flush_interval: float = 1.0, max_buffer: int = 50):
        self.task_id = task_id
        self.flush_interval = flush_interval
        self.max_buffer = max_buffer
        self._buffer: List[Tuple[str, str]] = []
        self._last_flush = time.time()
        self._lock = threading.Lock()

    def add(self, level: str, message: str):
        with self._lock:
            self._buffer.append((level, message))
            now = time.time()
            if len(self._buffer) >= self.max_buffer or (now - self._last_flush) >= self.flush_interval:
                self._flush_locked()

    def flush(self):
        with self._lock:
            self._flush_locked()

    def _flush_locked(self):
        if not self._buffer:
            self._last_flush = time.time()
            return
        db = get_thread_db()
        try:
            log_objects = [
                models.SyncLog(task_id=self.task_id, level=lvl, message=msg)
                for lvl, msg in self._buffer
            ]
            db.bulk_save_objects(log_objects)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to flush logs for task {self.task_id}: {e}")
        finally:
            self._buffer.clear()
            self._last_flush = time.time()


class GitSyncExecutor:
    def __init__(self):
        self.work_dir = os.path.abspath(settings.sync_work_dir)
        os.makedirs(self.work_dir, exist_ok=True)

    def _run_cmd(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        capture: bool = True,
        timeout: Optional[int] = 120,
    ) -> Tuple[int, str, str]:
        logger.info(f"Running command: {' '.join(cmd)} (cwd={cwd})")
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=capture,
                text=True,
                timeout=timeout,
            )
            return proc.returncode, proc.stdout or "", proc.stderr or ""
        except subprocess.TimeoutExpired as e:
            return -1, e.stdout or "", f"Command timed out after {timeout}s: {str(e)}"
        except Exception as e:
            return -1, "", f"Failed to run command: {str(e)}"

    def _log_line(self, log_buffer: LogBuffer, message: str, level: str = "INFO"):
        log_buffer.add(level, message)

    def _update_task(
        self,
        task_id: int,
        status: Optional[models.SyncStatus] = None,
        progress: Optional[int] = None,
        stage: Optional[str] = None,
        message: Optional[str] = None,
    ):
        db = get_thread_db()
        max_retries = 5
        for attempt in range(max_retries):
            try:
                crud.update_task_status(db, task_id, status, progress, stage, message)
                return
            except Exception as e:
                db.rollback()
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    logger.error(f"Failed to update task {task_id} after {max_retries} attempts: {e}")

    def sync_repo(self, task_id: int, repo: models.Repo):
        log_buffer = LogBuffer(task_id)

        self._log_line(log_buffer, f"开始同步仓库: {repo.name}", "INFO")
        self._log_line(log_buffer, f"源地址: {repo.source_url}", "DEBUG")
        self._log_line(log_buffer, f"目标地址: {repo.target_url}", "DEBUG")
        log_buffer.flush()

        db = get_thread_db()
        try:
            for attempt in range(3):
                try:
                    crud.mark_task_started(db, task_id)
                    break
                except Exception as e:
                    db.rollback()
                    if attempt == 2:
                        self._log_line(log_buffer, f"标记任务启动失败: {e}", "ERROR")
                        log_buffer.flush()
                        return False
                    time.sleep(0.2)
        except Exception as e:
            self._log_line(log_buffer, f"初始化失败: {e}", "ERROR")
            log_buffer.flush()
            return False

        mirror_dir = os.path.join(self.work_dir, f"{repo.name}.git")
        success = False
        error_msg = ""

        try:
            self._update_task(
                task_id,
                status=models.SyncStatus.CLONING,
                progress=10,
                stage="clone",
                message="正在克隆源仓库 (mirror 模式)",
            )
            self._log_line(log_buffer, "步骤 1/3: 克隆源仓库 (git clone --mirror)", "INFO")

            if os.path.exists(mirror_dir):
                self._log_line(log_buffer, f"清理旧的镜像目录: {mirror_dir}", "DEBUG")
                shutil.rmtree(mirror_dir)

            log_buffer.flush()
            clone_cmd = ["git", "clone", "--mirror", repo.source_url, mirror_dir]
            rc, out, err = self._run_cmd(clone_cmd)
            if out:
                self._log_line(log_buffer, f"clone stdout:\n{out.strip()}", "DEBUG")
            if err:
                self._log_line(log_buffer, f"clone stderr:\n{err.strip()}", "DEBUG")

            if rc != 0:
                error_msg = f"克隆失败 (exit {rc}): {err.strip() or out.strip()}"
                self._log_line(log_buffer, error_msg, "ERROR")
                raise RuntimeError(error_msg)

            self._update_task(
                task_id,
                progress=50,
                stage="clone_done",
                message="源仓库克隆完成",
            )
            self._log_line(log_buffer, "源仓库克隆完成", "INFO")

            self._update_task(
                task_id,
                status=models.SyncStatus.PUSHING,
                progress=55,
                stage="remote_check",
                message="检查并配置备份远程仓库地址",
            )
            self._log_line(log_buffer, "步骤 2/3: 配置备份远程仓库", "INFO")

            rc, remote_out, remote_err = self._run_cmd(
                ["git", "remote", "-v"], cwd=mirror_dir
            )
            if "backup" not in remote_out:
                rc2, _, err2 = self._run_cmd(
                    ["git", "remote", "add", "backup", repo.target_url],
                    cwd=mirror_dir,
                )
                if rc2 != 0:
                    error_msg = f"添加 backup remote 失败: {err2.strip()}"
                    self._log_line(log_buffer, error_msg, "ERROR")
                    raise RuntimeError(error_msg)
            else:
                rc2, _, err2 = self._run_cmd(
                    ["git", "remote", "set-url", "backup", repo.target_url],
                    cwd=mirror_dir,
                )
                if rc2 != 0:
                    self._log_line(log_buffer, f"设置 backup remote 警告: {err2.strip()}", "WARN")

            self._update_task(
                task_id,
                progress=65,
                stage="push",
                message="正在推送到备份服务器 (mirror push)",
            )
            self._log_line(log_buffer, "步骤 3/3: 推送到备份服务器 (git push --mirror backup)", "INFO")
            log_buffer.flush()

            rc, push_out, push_err = self._run_cmd(
                ["git", "push", "--mirror", "backup"],
                cwd=mirror_dir,
            )
            if push_out:
                self._log_line(log_buffer, f"push stdout:\n{push_out.strip()}", "DEBUG")
            if push_err:
                self._log_line(log_buffer, f"push stderr:\n{push_err.strip()}", "DEBUG")

            if rc != 0:
                error_msg = f"推送失败 (exit {rc}): {push_err.strip() or push_out.strip()}"
                self._log_line(log_buffer, error_msg, "ERROR")
                raise RuntimeError(error_msg)

            self._update_task(
                task_id,
                status=models.SyncStatus.SUCCESS,
                progress=100,
                stage="done",
                message="同步成功完成",
            )
            self._log_line(log_buffer, f"仓库 {repo.name} 同步成功！", "INFO")
            success = True

        except Exception as e:
            error_msg = str(e)
            self._update_task(
                task_id,
                status=models.SyncStatus.FAILED,
                stage="error",
                message=error_msg[:400],
            )
            self._log_line(log_buffer, f"同步异常: {error_msg}", "ERROR")
        finally:
            log_buffer.flush()
            if os.path.exists(mirror_dir):
                try:
                    shutil.rmtree(mirror_dir)
                    self._log_line(log_buffer, f"临时镜像目录已清理: {mirror_dir}", "DEBUG")
                except Exception as ce:
                    self._log_line(log_buffer, f"清理目录失败: {ce}", "WARN")
                log_buffer.flush()

        return success


class SyncTaskManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.executor = GitSyncExecutor()
        self.task_queue: "queue.Queue[Tuple[int, int]]" = queue.Queue()
        self.active_tasks: Dict[int, threading.Thread] = {}
        self.max_workers = 3
        self._running = True
        for _ in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
        logger.info(f"SyncTaskManager started with {self.max_workers} persistent workers")

    def _worker_loop(self):
        while self._running:
            try:
                try:
                    task_id, repo_id = self.task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                self._run_task(task_id, repo_id)
            except Exception as e:
                logger.error(f"Worker loop exception: {e}", exc_info=True)
            finally:
                try:
                    self.task_queue.task_done()
                except ValueError:
                    pass

    def _run_task(self, task_id: int, repo_id: int):
        self.active_tasks[task_id] = threading.current_thread()
        try:
            db = get_thread_db()
            try:
                repo = crud.get_repo(db, repo_id)
            except Exception as e:
                logger.error(f"Failed to get repo {repo_id}: {e}")
                repo = None
            if repo:
                self.executor.sync_repo(task_id, repo)
            else:
                logger.error(f"Repo not found: {repo_id}")
        finally:
            close_thread_db()
            self.active_tasks.pop(task_id, None)

    def submit_task(self, task_id: int, repo_id: int):
        self.task_queue.put((task_id, repo_id))
        logger.info(f"Submitted sync task {task_id} for repo {repo_id}")

    def submit_tasks(self, items: List[Tuple[int, int]]):
        for task_id, repo_id in items:
            self.task_queue.put((task_id, repo_id))
            logger.info(f"Submitted sync task {task_id} for repo {repo_id}")

    def get_running_count(self) -> int:
        return len(self.active_tasks)

    def get_queue_size(self) -> int:
        return self.task_queue.qsize()


sync_manager = SyncTaskManager()
