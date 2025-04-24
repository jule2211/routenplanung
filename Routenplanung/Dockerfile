# ✅ Basis-Image mit Python
FROM python:3.10-slim

# ✅ Arbeitsverzeichnis im Container
WORKDIR /app

# ✅ requirements.txt ins Image kopieren und Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Anwendungscode ins Image kopieren
COPY Routenplanung_Vorhersage.py flask_app.py station_departures.pkl ./


# ✅ Flask-App starten
CMD ["python", "flask_app.py"]
