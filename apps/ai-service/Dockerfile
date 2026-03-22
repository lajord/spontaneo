FROM python:3.10-slim
WORKDIR /app

# --- ai-service ---
COPY ai-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ai-service/app/ ./app/

# --- Agent de recherche (Test_IA_CANDIDATURE) ---
COPY Test_IA_CANDIDATURE/Agent_Extraction_Data/ ./agent_pkg/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
