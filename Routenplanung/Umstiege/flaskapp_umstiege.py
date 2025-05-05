from flask import Flask, request, jsonify
from datetime import datetime
import pickle
from umstiege import analyse_and_replan

app = Flask(__name__)

# 🛤️ station_departures einmal beim Start laden
with open("station_departure.pkl", "rb") as f:
    station_departures = pickle.load(f)
print("✅ station_departures geladen")

# 🔧 Test-Endpunkt zur schnellen Prüfung, ob die API läuft
@app.route("/", methods=["GET"])
def hello():
    return "API läuft ✅"

# 🛤️ POST-Endpunkt für Analyse und Re-Planung
@app.route("/api/analyse_and_replan", methods=["POST"])
def api_analyse_and_replan():
    try:
        data = request.get_json()

        detailed_routes = data['detailed_routes']
        # travel_date brauchen wir nicht mehr!

        # Datumsfelder konvertieren, falls nötig
        for route in detailed_routes:
            for abschnitt in route:
                if isinstance(abschnitt["planned_departure_from"], str):
                    abschnitt["planned_departure_from"] = datetime.fromisoformat(abschnitt["planned_departure_from"])
                if isinstance(abschnitt["planned_arrival_to"], str):
                    abschnitt["planned_arrival_to"] = datetime.fromisoformat(abschnitt["planned_arrival_to"])
                # ✨ hinzugefügt: planned_arrival_date_from von String zu date-Objekt machen
                if "planned_arrival_date_from" in abschnitt and isinstance(abschnitt["planned_arrival_date_from"], str):
                    abschnitt["planned_arrival_date_from"] = datetime.fromisoformat(abschnitt["planned_arrival_date_from"]).date()

        # 🚀 Hauptlogik aufrufen
        analysed_routes = analyse_and_replan(detailed_routes, station_departures)

        return jsonify({
            "status": "success",
            "analysed_routes": analysed_routes
        }), 200

    except Exception as e:
        print("❌ Fehler in /api/analyse_and_replan:", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8005, debug=True)
