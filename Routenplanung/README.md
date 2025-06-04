# Route planning API

This API calculates optimal train connections between two stations based on a predefined timetable. Planned departure and arrival times as well as transfer times are taken into account. The connection search is based on a DIJKSTRA-like algorithm. The data comes from a precalculated pickle file based on the planned timetable in the database.

## Project structure

- `flaskapp.py`: Flask server with API endpoints
- `routenberechnung.py`: Contains the logic for route planning
- `station_departure.pkl`: Pickle file with precalculated departure data
- `requirements.txt`: Python dependencies
- `Dockerfile`: Container definition for execution with Docker

---

## Start application

### 1. Directly with Python (locally)

Prerequisite: Python 3.10+ is installed

```bash

# Install dependencies
pip install -r requirements.txt

# Start Flask app
python flaskapp.py
```


The API can then be accessed at `http://localhost:8000`.

### 2. With Docker

```bash
# build image
docker build -t routenplanung-api .

# start container
docker run -p 8000:8000 routenplanung-api
```

---

## Example request

You can request a connection using the following GET endpoint:

```
GET /route?source=Berlin&target=München&date=2025-06-01&time=08:30
```

### Example with curl:

```bash
curl "http://localhost:8000/route?source=Berlin&target=München&date=2025-06-01&time=08:30"
```

### Explanation of parameters:

| Parameter | Description                      | Example          |
|-----------|-----------------------------------|-------------------|
| `source`  | Starting station                     | `Berlin`          |
| `target`  | Destination station                     | `München`         |
| `date`    | Travel date in the format `YYYY-MM-DD` | `2025-05-26`      |
| `time`    | Departure time in the format `HH:MM`    | `08:00`           |

---

## Example-Response
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

## Key methods (`routenberechnung.py`)

| Method | Description |
|--------|--------------|
| `routenplanung()` | Calculates (up to) four optimal train connections from a starting station to a destination station. |
| `filter_and_sort_routes()` | 
Selects the best connections from all routes found, taking into account transfers and arrival times. |
| `verarbeite_verbindungen()` | The actual routing algorithm. Uses a priority queue (heap) for route calculation. |
| `reconstruct_route_details(...)` | Rekonstruiert, ausgehend vom Zielknoten, eine vollständige Zugverbindung.  |
| `create_station_departures_from_db()` | Reconstructs a complete train connection starting from the destination node. |

---

## Data

- `station_departure.pkl` Contains all known departures for each station (based on the planned timetable in the database), sorted by departure time
- The file was created based on the sollfahrplan_reihenfolge table and reduces access to connections per station to a simple dictionary lookup

---

## requirements


- flask
- pandas
- psycopg2

##  responsibility

Jule
---

