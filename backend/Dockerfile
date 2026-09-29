FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer fonts-liberation && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app.py backend/app.py
COPY ["2026-09 Total Energies.docx", "2026-09 Total Energies.docx"]
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn","backend.app:app","--host","0.0.0.0","--port","8080","--proxy-headers"]

