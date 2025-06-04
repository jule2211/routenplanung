from flask import Flask, request, jsonify
import pickle
from datetime import datetime
from routenberechnung import routenplanung   

app = Flask(__name__)

# station_departures einmal beim Start laden
with open("station_departure.pkl", "rb") as f:
    station_departures = pickle.load(f)
print("✅ station_departures geladen")

# Test-Endpunkt zur schnellen Prüfung, ob die API läuft
@app.route("/", methods=["GET"])
def hello():
    return "API läuft ✅"


@app.route("/route", methods=["GET"])
def get_route():
    source = request.args.get("source")
    target = request.args.get("target")
    date_str = request.args.get("date")          # Format: YYYY-MM-DD
    time_str = request.args.get("time")          # Format: HH:MM

    if not source or not target or not date_str or not time_str:
        return jsonify({"error": "Fehlende Parameter"}), 400

    try:
        travel_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        departure_time = datetime.combine(travel_date, datetime.strptime(time_str, "%H:%M").time())
    except ValueError:
        return jsonify({"error": "Ungültiges Datums- oder Zeitformat"}), 400

    routes = routenplanung(
        source=source,
        target=target,
        station_departures=station_departures,
        departure_time=departure_time,
        travel_date=travel_date
    )

    if not routes:
        return jsonify({"message": "Keine Verbindung gefunden"})

    return jsonify(routes)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)


