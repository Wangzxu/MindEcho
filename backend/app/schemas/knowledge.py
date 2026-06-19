# -*- coding: utf-8 -*-
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class KnowledgeImportCreate(BaseModel):
    file_name: str = Field(..., description="上传的文件名称")
    file_hash: str = Field(..., description="文件 SHA-256 哈希")
    minio_bucket: str = Field(..., description="MinIO Bucket桶名")
    minio_object_name: str = Field(..., description="MinIO 物理存储对象名")
    file_size: int = Field(..., description="文件大小（字节）")

class KnowledgeImportResponse(BaseModel):
    id: int
    file_name: str
    file_hash: str
    minio_bucket: str
    minio_object_name: str
    file_size: int
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
