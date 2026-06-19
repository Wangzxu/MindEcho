# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional

# 定义泛型数据模型变量
T = TypeVar("T")

class Result(BaseModel, Generic[T]):
    """
    统一响应返回结构
    """
    code: int = Field(200, description="业务状态码")
    data: Optional[T] = Field(None, description="业务数据内容")
    message: str = Field("操作成功", description="响应提示信息")

    @classmethod
    def success(cls, data: T = None, message: str = "操作成功"):
        return cls(code=200, data=data, message=message)

    @classmethod
    def error(cls, code: int = 500, message: str = "操作失败", data: Optional[T] = None):
        return cls(code=code, data=data, message=message)
