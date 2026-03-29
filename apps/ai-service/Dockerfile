FROM python:3.10-slim
WORKDIR /app

# --- ai-service ---
COPY ai-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ai-service/app/ ./app/

# --- Agent de recherche (LangGraph) ---
COPY agent/ ./agent/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
