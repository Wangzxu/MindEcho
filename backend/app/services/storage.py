# -*- coding: utf-8 -*-
import io
import logging
from minio import Minio
from config import Config

logger = logging.getLogger(__name__)

class StorageService:
    """MinIO 对象存储服务封装"""
    def __init__(self):
        self.client = None
        self.bucket_name = None

    def init_service(self):
        """根据 Config 初始化 MinIO 客户端"""
        self.bucket_name = Config.MINIO_BUCKET
        try:
            # 建立 Minio 客户端连接
            self.client = Minio(
                endpoint=Config.MINIO_ENDPOINT,
                access_key=Config.MINIO_ACCESS_KEY,
                secret_key=Config.MINIO_SECRET_KEY,
                secure=Config.MINIO_SECURE
            )
            # 校验并创建 bucket
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"成功在 MinIO 创建存储桶: {self.bucket_name}")
            else:
                logger.info(f"已连接至 MinIO 存储桶: {self.bucket_name}")
        except Exception as e:
            logger.error(f"MinIO 客户端连接或初始化存储桶失败: {str(e)}。文件上传将降级为只写入向量库模式。")
            self.client = None

    def upload_file(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        """
        上传二进制文件流到 MinIO 存储桶
        """
        if not self.client:
            logger.warning(f"MinIO 客户端未就绪，跳过物理文件写入 (目标路径: {object_name})")
            return False
        try:
            data_stream = io.BytesIO(data)
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=data_stream,
                length=len(data),
                content_type=content_type
            )
            logger.info(f"成功将文件物理备份至 MinIO: {self.bucket_name}/{object_name}")
            return True
        except Exception as e:
            logger.error(f"文件上传至 MinIO 发生异常: {str(e)}")
            return False

# 导出单例
storage_service = StorageService()
