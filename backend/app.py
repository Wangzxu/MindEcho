# -*- coding: utf-8 -*-
import sys

print("=" * 60)
print("【提示】后端入口文件已重构迁移至 main.py。")
print("这是为了解决 Uvicorn reload 时将 app.py 与 app/ 文件夹冲突")
print("从而导致 'Attribute \"app\" not found in module \"app\"' 的报错。")
print("")
print("请使用以下命令启动后端服务:")
print("    python main.py")
print("=" * 60)

sys.exit(0)
