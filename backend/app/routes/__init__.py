# -*- coding: utf-8 -*-
from app.routes.health import health_bp
from app.routes.chat import chat_bp
from app.routes.auth import auth_bp, get_current_user
from app.routes.admin import admin_bp

__all__ = ["health_bp", "chat_bp", "auth_bp", "get_current_user", "admin_bp"]

