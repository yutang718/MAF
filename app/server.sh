#!/bin/bash

# 设置 Python 路径
export PYTHONPATH=$PYTHONPATH:/Users/tangyu/Projects/MAF

# 启动 FastAPI 服务器
uvicorn main:app --host 0.0.0.0 --port 8000 --reload 