# Delay-Aware Route Replanning API

This project provides a Flask API that analyzes train routes and replans them if a transfer is likely to fail due to a delay. It also returns the total delay probability and the expected total delay of the route.

## Functionality

The API receives routes with predicted delays, checks whether a transfer is at risk, and, if necessary, searches for an alternative route from the transfer station to the destination station. It also calculates the the total delay probability and the expected total delay of the route based on the predicted delays.

## Files and Structure

- `flaskapp.py`: The main Flask application for the API.
- `replan.py`: Contains the core logic for checking transfer safety, replanning and calculating the total delay probability.
- `routenberechnung.py`: Contains the route planning logic.
- `station_departure.pkl`: Contains all known departures for each station (required for route planning).
- `requirements.txt`: List of required Python packages.
- `Dockerfile`: Containerization of the Flask app for deployment.

## Key methods

- replan(): Checks if a transfer is at risk. If so, finds an alternative route from the transfer station to the final destination.
- berechne_gesamtverspaetungswahrscheinlichkeit(): Computes the probability that the route will arrive on time, based on delay category probabilities.
- analyse_and_replan(): Analyzes a full route and attempts replanning if needed.


## API Endpoints

### `GET /`
Simple health check of the API.

---

### `POST /api/analyse_and_replan`

This endpoint analyzes a list of route segments and checks whether any transfers are at risk. If necessary, it plans a new route from the critical station.

**Input:**
```json
{
  "detailed_routes": [[
    {
      "station_from": "Berlin Hbf",
      "station_to": "Hannover Hbf",
      "planned_departure_from": "2025-06-04T12:30:00",
      "planned_arrival_to": "2025-06-04T14:00:00",
      "train_number": 525.0,
      "departure_date": "2025-06-04",
      "zugtyp": "ICE",
      "umsteigeort": "Nürnberg Hbf",
      "umsteigezeit_minuten": 12,
      "predicted_delay": 12,
      "category_probabilities": {
        "On time": 60,
        "1-9 min": 20,
        "10-19 min": 10,
        "20-29 min": 5,
        "30+ min": 5
      }
    },
    ...
  ]]
}
```

**Output:**
```json
{
  "status": "success",
  "analysed_routes": [
    {
      "urspruengliche_route": [...],
      "alternative_routeninfos": [...],
      "erwartete_gesamtverspaetung_minuten": 18.5,
      "gesamtverspaetungswahrscheinlichkeit": 74.6
    }
  ]
}
```

If no replanning is necessary, the field `"alternative_routeninfos"` remains empty.

## Docker Usage

You can build and run the API using Docker:

```bash
docker build -t replan-api .
docker run -p 9003:9003 replan-api
```

The API will then be available at `http://localhost:9003`.

## Requirements

Install the required packages (if not using Docker):

```bash
pip install -r requirements.txt
```

---

## Notes

- The file `station_departure.pkl` must exist in the same directory. It contains all station departure data and is required for replanning.
- The logic is modular and can be extended for integration into larger systems.

---

## Example Use Case

- The system checks whether a transfer is in danger.
- If so, it plans a new route from the current station to the destination.
- At the same time, it calculates how likely the entire route is to be delayed and what the total delay probability is.

---