#!/usr/bin/env python3
"""初始化 cc1 ~ cc10 共 10 个仓库到数据库"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app import models, crud, schemas
from app.config import settings


def main():
    Base.metadata.create_all(bind=engine)
    backup_prefix = settings.backup_remote_prefix.rstrip("/")
    repos_data = []

    for i in range(1, 11):
        name = f"cc{i}"
        repos_data.append(
            schemas.RepoCreate(
                name=name,
                source_url=f"https://github.com/cc-demo/{name}.git",
                target_url=f"{backup_prefix}/{name}.git",
                description=f"GitHub 仓库 {name} 镜像备份",
                is_active=1,
            )
        )

    db = SessionLocal()
    try:
        created = crud.create_repos_bulk(db, repos_data)
        print(f"已初始化 {len(created)} 个仓库：")
        for r in created:
            print(f"  - {r.name}: {r.source_url} -> {r.target_url}")

        total = len(crud.get_repos(db))
        print(f"\n数据库中现有仓库总数: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
