# 🚆 Routenplanung API

Diese API berechnet optimale Zugverbindungen zwischen zwei Bahnhöfen auf Basis eines vordefinierten Fahrplans. Dabei werden geplante Abfahrts- und Ankunftszeiten sowie Umstiegszeiten berücksichtigt. Die Verbindungssuche basiert auf einem DIJKSTRA-ähnlichen Algorithmus. Die Daten stammen aus einer vorberechneten Pickle-Datei, die auf dem geplanten Fahrplan in der Datenbank basiert.

## 🔧 Projektstruktur

- `flaskapp.py`: Flask-Server mit API-Endpunkten
- `routenberechnung.py`: Beinhaltet die Logik zur Routenplanung
- `station_departure.pkl`: Pickle-Datei mit vorberechneten Abfahrtsdaten
- `requirements.txt`: Python-Abhängigkeiten
- `Dockerfile`: Containerdefinition zur Ausführung mit Docker

---

## 🚀 Anwendung starten

### 1. Mit Python direkt (lokal)

Voraussetzung: Python 3.10+ ist installiert

```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# Flask-App starten
python flaskapp.py
```

Die API ist dann unter `http://localhost:8000` erreichbar.

### 2. Mit Docker

```bash
# Image bauen
docker build -t routenplanung-api .

# Container starten
docker run -p 8000:8000 routenplanung-api
```

---

## 📡 Beispiel-Request

Du kannst eine Verbindung über folgenden GET-Endpunkt anfragen:

```
GET /route?source=Berlin&target=München&date=2025-06-01&time=08:30
```

### Beispiel mit curl:

```bash
curl "http://localhost:8000/route?source=Berlin&target=München&date=2025-06-01&time=08:30"
```

### Erklärung der Parameter:

| Parameter | Beschreibung                      | Beispiel          |
|-----------|-----------------------------------|-------------------|
| `source`  | Startbahnhof                      | `Berlin`          |
| `target`  | Zielbahnhof                       | `München`         |
| `date`    | Reisedatum im Format `YYYY-MM-DD` | `2025-05-26`      |
| `time`    | Abfahrtszeit im Format `HH:MM`    | `08:00`           |

---

## Beispiel-Response
```json
[
  {
    "station_name_from": "Berlin Hbf",
    "station_name_to": "Leipzig Hbf",
    "planned_departure_from": "2025-05-26T08:00:00",
    "planned_arrival_to": "2025-05-26T09:10:00",
    "train_number": "ICE 1001",
    "planned_arrival_date_from": "2025-05-26",
    "zugtyp": "ICE",
    "halt_nummer": 5,
    "train_avg_30": 0.15,
    "station_avg_30": 0.18,
    "umsteigeort": null,
    "umsteigezeit_minuten": null
  },
  {
    "station_name_from": "Leipzig Hbf",
    "station_name_to": "Nürnberg Hbf",
    "planned_departure_from": "2025-05-26T09:30:00",
    "planned_arrival_to": "2025-05-26T10:00:00",
    "train_number": "ICE 1203",
    "planned_arrival_date_from": "2025-05-26",
    "zugtyp": "ICE",
    "halt_nummer": 3,
    "train_avg_30": 0.12,
    "station_avg_30": 0.20,
    "umsteigeort": "Halle(Saale)Hbf",
    "umsteigezeit_minuten": 20.0
  },
  {
    "station_name_from": "Nürnberg Hbf",
    "station_name_to": "München Hbf",
    "planned_departure_from": "2025-05-26T10:15:00",
    "planned_arrival_to": "2025-05-26T12:00:00",
    "train_number": "ICE 800",
    "planned_arrival_date_from": "2025-05-26",
    "zugtyp": "ICE",
    "halt_nummer": 7,
    "train_avg_30": 0.25,
    "station_avg_30": 0.30,
    "umsteigeort": "Erfurt Hbf",
    "umsteigezeit_minuten": 15.0
  }
]
```

---

## 🧠 Zentrale Methoden (`routenberechnung.py`)

| Methode | Beschreibung |
|--------|--------------|
| `routenplanung(start, ziel, abfahrt, max_routes=6)` | Hauptfunktion zur Berechnung der besten Routen. |
| `reconstruct_route_details(...)` | Erzeugt eine detailreiche Beschreibung einer Route. |
| `calculate_total_delay_probability(...)` | Schätzt die Wahrscheinlichkeit, dass die Route verspätet ankommt. |
| `get_station_departures_from_pickle()` | Lädt die Verbindungsdaten aus `station_departure.pkl`. |

---

## 📦 Daten

- `station_departure.pkl` enthält alle geplanten Verbindungen zwischen Bahnhöfen mit Abfahrts- und Ankunftszeiten, Zugnummern und Haltereihenfolge.
- Die Datei wurde basierend auf der Tabelle sollfahrplan_reihenfolge erstellt und reduziert den Zugriff auf Verbindungen pro Bahnhof auf einen einfachen Dictionary-Lookup

---

## 🛠 Voraussetzungen

- flask
- pandas
- psycopg2


---



## ✅ Test

Rufe einfach folgenden Endpunkt auf, um zu prüfen, ob die API läuft:

```
GET /
```

Antwort:

```
API läuft ✅
```