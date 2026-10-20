"""数据库连接与会话。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表，并对已存在的表补充新增列（create_all 不会修改已有表）。"""
    # 导入模型以注册到 Base.metadata
    from app.models import task, segment, glossary, user, translation_record, translation_cache  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


# 轻量迁移映射：{表名: {列名: 列类型}}，类型使用 SQLite/PostgreSQL 通用写法
_LIGHTWEIGHT_MIGRATIONS = {
    "tasks": {
        "translated_count": "INTEGER",
        "total_count": "INTEGER",
    },
}


def _run_lightweight_migrations():
    """为已有表执行 ALTER TABLE ADD COLUMN，容忍列已存在的情况。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.connect() as conn:
        for table, columns in _LIGHTWEIGHT_MIGRATIONS.items():
            if table not in inspector.get_table_names():
                continue  # 新表由 create_all 直接建成
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col, col_type in columns.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        conn.commit()
