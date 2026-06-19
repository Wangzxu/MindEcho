# -*- coding: utf-8 -*-
from flask import jsonify

class Result:
    """
    统一前后端数据交互响应包装类
    结构包含:
      - code: 业务状态码 (通常 200 表示成功，其他表示各类业务异常)
      - data: 响应数据内容
      - message: 提示信息
    """

    def __init__(self, code: int, data=None, message: str = ""):
        self.code = code
        self.data = data
        self.message = message

    def to_dict(self) -> dict:
        """转换为字典格式，方便 JSON 序列化"""
        return {
            "code": self.code,
            "data": self.data,
            "message": self.message
        }

    def to_response(self, http_status_code: int = 200):
        """
        转换为 Flask 的 JSON Response 响应对象
        :param http_status_code: HTTP 状态码，默认使用 200 状态码
        """
        return jsonify(self.to_dict()), http_status_code

    @classmethod
    def success(cls, data=None, message: str = "操作成功"):
        """
        成功响应便捷方法 (默认业务码 200)
        """
        return cls(code=200, data=data, message=message)

    @classmethod
    def error(cls, code: int = 500, message: str = "操作失败", data=None):
        """
        异常响应便捷方法 (默认业务码 500)
        """
        return cls(code=code, data=data, message=message)

    @classmethod
    def bad_request(cls, message: str = "请求参数错误", data=None):
        """
        客户端参数错误响应 (业务码 400)
        """
        return cls(code=400, data=data, message=message)

    @classmethod
    def unauthorized(cls, message: str = "未授权，请先登录", data=None):
        """
        未认证授权响应 (业务码 401)
        """
        return cls(code=401, data=data, message=message)

    @classmethod
    def forbidden(cls, message: str = "无权访问此资源", data=None):
        """
        无权访问响应 (业务码 403)
        """
        return cls(code=403, data=data, message=message)

    @classmethod
    def not_found(cls, message: str = "请求的资源未找到", data=None):
        """
        资源未找到响应 (业务码 404)
        """
        return cls(code=404, data=data, message=message)
