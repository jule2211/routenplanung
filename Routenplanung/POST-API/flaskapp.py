from flask import Flask, request, jsonify
import pickle
from datetime import datetime
from routenberechnung import routenplanung  # Dein Routing-Modul importieren
# import requests  # Wird später gebraucht, wenn echte Vorhersage-API da ist

app = Flask(__name__)

# station_departures einmal beim Start laden
with open("station_departure.pkl", "rb") as f:
    station_departures = pickle.load(f)
print("✅ station_departures geladen")

# Dummy Funktion für Vorhersage
def request_delays(sections):
    # Hier später echten POST-Request einbauen
    print("⚡ Dummy-Vorhersage aufgerufen")
    return [0 for _ in sections]  # Dummy: keine Verspätung

# 🔧 Test-Endpunkt zur schnellen Prüfung, ob die API läuft
@app.route("/", methods=["GET"])
def hello():
    return "API läuft ✅"

# 🛤️ POST-Endpunkt für Routenplanung
@app.route("/route", methods=["POST"])
def get_route():
    if not request.is_json:
        return jsonify({"error": "Erwarte JSON-Body"}), 400

    data = request.get_json()

    source = data.get("source")
    target = data.get("target")
    date_str = data.get("date")          # Format: YYYY-MM-DD
    time_str = data.get("time")           # Format: HH:MM

    if not source or not target or not date_str or not time_str:
        return jsonify({"error": "Fehlende Parameter"}), 400

    try:
        travel_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        departure_time = datetime.combine(travel_date, datetime.strptime(time_str, "%H:%M").time())
    except ValueError:
        return jsonify({"error": "Ungültiges Datums- oder Zeitformat"}), 400

    # 🚂 Route berechnen
    routes = routenplanung(
        source=source,
        target=target,
        station_departures=station_departures,
        departure_time=departure_time,
        travel_date=travel_date
    )

    if not routes:
        return jsonify({"message": "Keine Verbindung gefunden"})

    # 🔮 Dummy Vorhersage für jede Strecke innerhalb der Route
    enhanced_routes = []
    for route in routes:
        sections = [
            {
                "station_name_from": leg["station_name_from"],
                "station_name_to": leg["station_name_to"],
                "planned_departure_from": leg["planned_departure_from"].strftime("%Y-%m-%d %H:%M"),
                "planned_arrival_to": leg["planned_arrival_to"].strftime("%Y-%m-%d %H:%M"),
                "train_number": leg["train_number"],
            }
            for leg in route
        ]

        # Hole Dummy-Verspätungen
        delays = request_delays(sections)

        # Kombiniere
        for i, delay in enumerate(delays):
            route[i]["predicted_delay_minutes"] = delay

        enhanced_routes.append(route)

    return jsonify(enhanced_routes)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

