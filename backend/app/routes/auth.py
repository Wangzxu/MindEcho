# -*- coding: utf-8 -*-
import logging
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from config import Config
from app.database.mysql import get_db
from app.models import User, UserProfile
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserResponse
from app.schemas.base import Result
from app.services.auth_service import auth_service

auth_bp = APIRouter(prefix="/api/auth", tags=["用户认证"])
logger = logging.getLogger(__name__)

# 安全承载头提取器 (Bearer Token)
security_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    依赖注入方法：校验请求头中的 JWT 令牌并提取当前登录用户
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证已失效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 解码校验 Token
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError as e:
        logger.warning(f"JWT Token 校验解密失败: {str(e)}")
        raise credentials_exception
        
    # 查询用户实体
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
        
    # 检查激活状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该账户尚未激活或已被停用，请联系管理员"
        )
        
    return user


def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    依赖注入：验证当前登录用户是否具备管理员角色，不匹配则拒绝访问。
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是管理员账号，无权调阅此教师端管理接口"
        )
    return current_user


@auth_bp.post("/register", response_model=Result[UserResponse], status_code=status.HTTP_201_CREATED)
def register_user(data: UserRegister, db: Session = Depends(get_db)):
    """
    学生/用户注册接口
    """
    username = data.username.strip()
    nickname = data.nickname.strip() if data.nickname else None

    # 1. 检测重名
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在，请更换后重试"
        )

    try:
        # 2. 密码加盐哈希
        hashed_password = auth_service.hash_password(data.password)

        # 3. 创建用户并同步在同一事务中初始化心理画像表
        new_user = User(
            username=username,
            password_hash=hashed_password,
            role="student",  # 默认注册角色为普通学生
            is_active=True   # 默认激活
        )
        db.add(new_user)
        db.flush()  # 刷入数据库以获取自动生成的自增 user.id

        # 4. 创建关联的空心理画像记录
        new_profile = UserProfile(
            user_id=new_user.id,
            nickname=nickname or username,
            core_stressors=[],
            effective_coping_methods=[],
            entity_relation_map={},
            semantic_history_recall=""
        )
        db.add(new_profile)
        
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"新用户注册成功: {username} (ID: {new_user.id})")
        return Result.success(data=UserResponse.model_validate(new_user), message="注册成功")
    except Exception as e:
        db.rollback()
        logger.error(f"注册用户写入数据库异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败，数据库服务异常: {str(e)}"
        )


@auth_bp.post("/login", response_model=Result[TokenResponse])
def login_user(data: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录接口 (校验密码成功后签发 Bearer JWT Token)
    """
    username = data.username.strip()
    password = data.password

    # 1. 查找用户
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或密码不正确"
        )

    # 2. 验证是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户未激活，无权登录"
        )

    # 3. 校验密码
    if not auth_service.verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或密码不正确"
        )

    # 4. 签发 Token
    token_payload = {
        "sub": user.username,
        "role": user.role,
        "id": user.id
    }
    
    access_token = auth_service.create_access_token(data=token_payload)
    
    logger.info(f"用户登录成功: {username}")
    return Result.success(
        data=TokenResponse(access_token=access_token),
        message="登录成功"
    )
