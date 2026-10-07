FROM node:24-bookworm-slim AS web-build
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHON_DOTENV_DISABLED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY cloud/requirements.txt ./cloud/requirements.txt
RUN pip install --no-cache-dir -r cloud/requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home app
COPY backend/npc_roles.py ./backend/npc_roles.py
COPY backend/relationship_manager.py ./backend/relationship_manager.py
COPY cloud/server.py ./cloud/server.py
COPY --from=web-build /build/web/dist ./web/dist
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "cloud.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
