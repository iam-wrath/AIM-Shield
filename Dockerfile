FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY attacks attacks
COPY rag_docs rag_docs
COPY eval eval
COPY --from=ui /ui/dist frontend/dist
# run as an unprivileged user; /data holds the event log (mounted as a volume by docker-compose.yml)
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown appuser /data
USER appuser
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
