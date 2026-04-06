from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(128), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BusinessApiKey(Base):
    __tablename__ = "business_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(String(64), unique=True, nullable=False)
    api_key_hash = Column(String(256), nullable=False)
    workspace_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
