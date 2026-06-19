# -*- coding: utf-8 -*-
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional
from config import Config
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """账户哈希密码校验与 JWT Token 鉴权核心服务"""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        对明文密码进行加盐哈希计算 (Bcrypt)
        """
        try:
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        except Exception as e:
            logger.error(f"密码哈希计算失败: {str(e)}")
            raise e

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        验证明文密码与数据库存储的哈希密文是否吻合
        """
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.warning(f"密码哈希校验失败/格式错误: {str(e)}")
            return False

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        生成 JWT 访问 Token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # 写入过期时间 payload
        to_encode.update({"exp": expire})
        
        try:
            encoded_jwt = jwt.encode(to_encode, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
            return encoded_jwt
        except Exception as e:
            logger.error(f"生成 JWT Token 失败: {str(e)}")
            raise e

# 导出单例
auth_service = AuthService()
