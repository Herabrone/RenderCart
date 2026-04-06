from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

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


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(128), unique=True, nullable=False, index=True)
    business_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    total_items = Column(Integer, nullable=False)
    completed_items = Column(Integer, nullable=False, default=0)
    failed_items = Column(Integer, nullable=False, default=0)
    pending_items = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    batch_metadata = Column("metadata", JSON, nullable=True)
    prompt = Column(Text, nullable=True)
    preset_id = Column(String(128), nullable=True)
    use_case = Column(String(64), nullable=True)
    product_category = Column(String(64), nullable=True)
    brand_style = Column(Text, nullable=True)
    brand_kit_id = Column(Integer, nullable=True, index=True)
    brand_kit_snapshot = Column(JSON, nullable=True)
    output_format = Column(String(64), nullable=True)
    mode = Column(String(64), nullable=True)
    batch_error = Column(Text, nullable=True)

    jobs = relationship("Job", back_populates="batch")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(128), unique=True, nullable=False, index=True)
    business_id = Column(String(64), nullable=False, index=True)
    batch_id = Column(
        String(128),
        ForeignKey("batch_jobs.batch_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    item_index = Column(Integer, nullable=True)
    item_label = Column(String(128), nullable=True)
    input_file_name = Column(String(256), nullable=True)
    original_image_url = Column(String(2048), nullable=True)
    status = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    image_url = Column(String(2048), nullable=True)
    prompt = Column(Text, nullable=True)
    preset_id = Column(String(128), nullable=True)
    use_case = Column(String(64), nullable=True)
    product_category = Column(String(64), nullable=True)
    brand_style = Column(Text, nullable=True)
    brand_kit_id = Column(Integer, nullable=True, index=True)
    brand_kit_snapshot = Column(JSON, nullable=True)
    output_format = Column(String(64), nullable=True)
    mode = Column(String(64), nullable=True)
    num_outputs = Column(Integer, nullable=True)
    callback_url = Column(String(2048), nullable=True)
    job_metadata = Column(JSON, nullable=True)
    actual_model = Column(String(128), nullable=True)
    inference_config_used = Column(JSON, nullable=True)
    progress = Column(Integer, nullable=True)
    step = Column(String(128), nullable=True)
    error = Column(Text, nullable=True)

    batch = relationship("BatchJob", back_populates="jobs")
    assets = relationship("Asset", back_populates="job", cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type = Column(String(64), nullable=False)
    label = Column(String(128), nullable=True)
    asset_url = Column(String(2048), nullable=False)
    storage_key = Column(String(1024), nullable=True, index=True)
    output_index = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_format = Column(String(32), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    asset_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="assets")


class BrandKit(Base):
    __tablename__ = "brand_kits"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    background = Column(String(256), nullable=False)
    lighting = Column(String(256), nullable=False)
    tone = Column(String(256), nullable=False)
    framing = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
