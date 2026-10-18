"""数据库初始化脚本：创建所有表。

首次运行或重置数据库时执行：
    python -m scripts.init_db
"""
from app.database import init_db, engine, Base
from app.models import task, segment, glossary  # noqa: F401


def init():
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成：", Base.metadata.tables.keys())


if __name__ == "__main__":
    init()
