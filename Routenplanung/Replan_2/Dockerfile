# Basis-Image
FROM python:3.11-slim

# Arbeitsverzeichnis erstellen
WORKDIR /app

# Benötigte System-Abhängigkeiten installieren
RUN apt-get update && apt-get install -y gcc libpq-dev && apt-get clean

# Requirements installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dein Projekt kopieren
COPY . .

# Startkommando (anpassen je nach Hauptdatei)
CMD ["python", "flaskapp_replan_2.py"]
