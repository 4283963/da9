import subprocess
import os
import shutil
import threading
import queue
import logging
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import crud, models
from app.config import settings

logger = logging.getLogger(__name__)


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
    ) -> tuple[int, str, str]:
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

    def _log_line(self, task_id: int, message: str, level: str = "INFO"):
        db = SessionLocal()
        try:
            crud.add_task_log(db, task_id, message, level)
        finally:
            db.close()

    def _update_task(
        self,
        task_id: int,
        status: Optional[models.SyncStatus] = None,
        progress: Optional[int] = None,
        stage: Optional[str] = None,
        message: Optional[str] = None,
    ):
        db = SessionLocal()
        try:
            crud.update_task_status(db, task_id, status, progress, stage, message)
        finally:
            db.close()

    def sync_repo(self, task_id: int, repo: models.Repo):
        self._log_line(task_id, f"开始同步仓库: {repo.name}", "INFO")
        self._log_line(task_id, f"源地址: {repo.source_url}", "DEBUG")
        self._log_line(task_id, f"目标地址: {repo.target_url}", "DEBUG")

        db = SessionLocal()
        try:
            crud.mark_task_started(db, task_id)
        finally:
            db.close()

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
            self._log_line(task_id, "步骤 1/3: 克隆源仓库 (git clone --mirror)", "INFO")

            if os.path.exists(mirror_dir):
                self._log_line(task_id, f"清理旧的镜像目录: {mirror_dir}", "DEBUG")
                shutil.rmtree(mirror_dir)

            clone_cmd = ["git", "clone", "--mirror", repo.source_url, mirror_dir]
            rc, out, err = self._run_cmd(clone_cmd)
            if out:
                self._log_line(task_id, f"clone stdout:\n{out.strip()}", "DEBUG")
            if err:
                self._log_line(task_id, f"clone stderr:\n{err.strip()}", "DEBUG")

            if rc != 0:
                error_msg = f"克隆失败 (exit {rc}): {err.strip() or out.strip()}"
                self._log_line(task_id, error_msg, "ERROR")
                raise RuntimeError(error_msg)

            self._update_task(
                task_id,
                progress=50,
                stage="clone_done",
                message="源仓库克隆完成",
            )
            self._log_line(task_id, "源仓库克隆完成", "INFO")

            self._update_task(
                task_id,
                status=models.SyncStatus.PUSHING,
                progress=55,
                stage="remote_check",
                message="检查并配置备份远程仓库地址",
            )
            self._log_line(task_id, "步骤 2/3: 配置备份远程仓库", "INFO")

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
                    self._log_line(task_id, error_msg, "ERROR")
                    raise RuntimeError(error_msg)
            else:
                rc2, _, err2 = self._run_cmd(
                    ["git", "remote", "set-url", "backup", repo.target_url],
                    cwd=mirror_dir,
                )
                if rc2 != 0:
                    self._log_line(task_id, f"设置 backup remote 警告: {err2.strip()}", "WARN")

            self._update_task(
                task_id,
                progress=65,
                stage="push",
                message="正在推送到备份服务器 (mirror push)",
            )
            self._log_line(task_id, "步骤 3/3: 推送到备份服务器 (git push --mirror backup)", "INFO")

            rc, push_out, push_err = self._run_cmd(
                ["git", "push", "--mirror", "backup"],
                cwd=mirror_dir,
            )
            if push_out:
                self._log_line(task_id, f"push stdout:\n{push_out.strip()}", "DEBUG")
            if push_err:
                self._log_line(task_id, f"push stderr:\n{push_err.strip()}", "DEBUG")

            if rc != 0:
                error_msg = f"推送失败 (exit {rc}): {push_err.strip() or push_out.strip()}"
                self._log_line(task_id, error_msg, "ERROR")
                raise RuntimeError(error_msg)

            self._update_task(
                task_id,
                status=models.SyncStatus.SUCCESS,
                progress=100,
                stage="done",
                message="同步成功完成",
            )
            self._log_line(task_id, f"仓库 {repo.name} 同步成功！", "INFO")
            success = True

        except Exception as e:
            error_msg = str(e)
            self._update_task(
                task_id,
                status=models.SyncStatus.FAILED,
                stage="error",
                message=error_msg[:400],
            )
            self._log_line(task_id, f"同步异常: {error_msg}", "ERROR")
        finally:
            if os.path.exists(mirror_dir):
                try:
                    shutil.rmtree(mirror_dir)
                    self._log_line(task_id, f"临时镜像目录已清理: {mirror_dir}", "DEBUG")
                except Exception as ce:
                    self._log_line(task_id, f"清理目录失败: {ce}", "WARN")

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
        self.task_queue: queue.Queue = queue.Queue()
        self.active_tasks: Dict[int, threading.Thread] = {}
        self.max_workers = 3
        self.worker_sem = threading.Semaphore(self.max_workers)
        self._start_dispatcher()

    def _start_dispatcher(self):
        t = threading.Thread(target=self._dispatch_loop, daemon=True)
        t.start()
        logger.info("Sync task dispatcher started")

    def _dispatch_loop(self):
        while True:
            try:
                task_id, repo_id = self.task_queue.get()
            except Exception:
                continue
            self.worker_sem.acquire()
            t = threading.Thread(
                target=self._run_task,
                args=(task_id, repo_id),
                daemon=True,
            )
            self.active_tasks[task_id] = t
            t.start()

    def _run_task(self, task_id: int, repo_id: int):
        try:
            db = SessionLocal()
            try:
                repo = crud.get_repo(db, repo_id)
            finally:
                db.close()
            if repo:
                self.executor.sync_repo(task_id, repo)
            else:
                logger.error(f"Repo not found: {repo_id}")
        finally:
            self.active_tasks.pop(task_id, None)
            self.worker_sem.release()
            self.task_queue.task_done()

    def submit_task(self, task_id: int, repo_id: int):
        self.task_queue.put((task_id, repo_id))
        logger.info(f"Submitted sync task {task_id} for repo {repo_id}")

    def submit_tasks(self, items: List[tuple[int, int]]):
        for task_id, repo_id in items:
            self.submit_task(task_id, repo_id)

    def get_running_count(self) -> int:
        return sum(1 for t in self.active_tasks.values() if t.is_alive())

    def get_queue_size(self) -> int:
        return self.task_queue.qsize()


sync_manager = SyncTaskManager()
