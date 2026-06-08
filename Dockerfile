# ── Stage 1: Build React Admin ────────────────────────────────
FROM node:20-slim AS admin-build

WORKDIR /admin
COPY admin/package*.json ./
RUN npm ci
COPY admin/ .
RUN npm run build

# ── Stage 2: Python App ───────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY requirements_portal.txt .
RUN pip install --no-cache-dir -r requirements_portal.txt

COPY . .

# Copiar build do React para a pasta estática do portal
COPY --from=admin-build /admin/dist ./portal/static/admin

EXPOSE 8080

CMD ["uvicorn", "portal.main:app", "--host", "0.0.0.0", "--port", "8080"]
