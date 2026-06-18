# ── Stage 1: Build React Admin ────────────────────────────────
FROM node:20-slim AS admin-build

WORKDIR /app
COPY admin/package*.json ./admin/
COPY admin/ ./admin/
COPY portal/static/ ./portal/static/
RUN cd admin && npm install && npm run build

# ── Stage 2: Python App ───────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY requirements_portal.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements_portal.txt

COPY . .

# Copiar build do React (Vite colocou em portal/static/admin)
COPY --from=admin-build /app/portal/static/admin ./portal/static/admin

EXPOSE 8080

CMD ["uvicorn", "portal.main:app", "--host", "0.0.0.0", "--port", "8080"]
