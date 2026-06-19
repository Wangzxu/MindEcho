# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import List

class HealthStatus(BaseModel):
    status: str
    mysql: str
    chromadb: str
    siliconflow: str
    warnings: List[str]
