FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM python:3.13-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=10000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY models ./models
COPY data ./data
COPY run.py ./
COPY --from=frontend /build/frontend/dist ./frontend/dist
USER 10001:10001
EXPOSE 10000
CMD ["python", "run.py"]
