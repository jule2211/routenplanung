# Basis-Image
FROM python:3.11-slim

# Arbeitsverzeichnis anlegen
WORKDIR /app

# Abhängigkeiten kopieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code kopieren
COPY . .

# Port freigeben (für Flask-Server)
EXPOSE 8005

# Startbefehl
CMD ["python", "flaskapp_umstiege.py"]
