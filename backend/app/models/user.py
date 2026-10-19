"""OAuth 登录用户模型。"""
from datetime import datetime

from sqlalchemy import Column, String, DateTime, BigInteger, Integer

from app.database import Base


class User(Base):
    __tablename__ = "users"

    # SQLite 仅对精确的 INTEGER PRIMARY KEY 自增，故 sqlite 方言降级为 Integer
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    github_login = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    html_url = Column(String(500), nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
