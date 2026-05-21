FROM python:3.11-slim
 
WORKDIR /app
 
COPY requirements_portal.txt .
RUN pip install --no-cache-dir -r requirements_portal.txt
 
COPY . .
 
EXPOSE 8080
 
CMD ["uvicorn", "portal.main:app", "--host", "0.0.0.0", "--port", "8080"]
 