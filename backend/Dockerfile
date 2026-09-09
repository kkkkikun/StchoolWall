# SchoolWall 后端镜像：python 3.10-slim + 依赖 + 代码
# 构建上下文必须是 backend/ 目录（docker build backend/ 或 compose 的 build.context）
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 依赖层（单独复制，代码改动不重装依赖）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 代码层
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
# pytest 仅测试用，镜像不带 tests/；.env 由 compose env_file 注入（绝不打进镜像）

# 上传文件目录（compose 挂卷覆盖）
ENV STATIC_BASE_DIR=/data/static
RUN mkdir -p /data/static
VOLUME /data/static

EXPOSE 8000

# 启动即跑迁移再起服务（单副本场景安全；多副本时改为部署前手动 migrate）
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
