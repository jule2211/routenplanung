# Basis-Image
FROM python:3.11-slim

# Setze das Arbeitsverzeichnis im Container
WORKDIR /app

# Kopiere alle Dateien ins Image
COPY . .

# Installiere System-Abhängigkeiten (z. B. für psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Starte die Flask-App
CMD ["python", "flaskapp.py"]

