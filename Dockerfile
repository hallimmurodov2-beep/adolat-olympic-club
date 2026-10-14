FROM node:22-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json tsconfig.json ./
RUN npm ci --ignore-scripts
COPY frontend ./frontend
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/tmp/olympiados
WORKDIR /app
COPY requirements.txt requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt \
    && groupadd --gid 10001 olympiados \
    && useradd --uid 10001 --gid olympiados --create-home olympiados \
    && (getent group 1000 >/dev/null || groupadd --gid 1000 render-secrets) \
    && usermod -a -G 1000 olympiados \
    && mkdir -p /tmp/olympiados \
    && chown olympiados:olympiados /tmp/olympiados
COPY --chown=olympiados:olympiados . .
COPY --from=frontend --chown=olympiados:olympiados /build/static/assets /app/static/assets
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/ready',timeout=3)" || exit 1
CMD ["sh", "scripts/container-start.sh"]
