from flask import Flask, request, jsonify
from datetime import datetime
import pickle
from replan import analyse_and_replan

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

        # Überprüfen, ob die erforderlichen Felder vorhanden sind
        if 'detailed_routes' not in data:
            return jsonify({
                "status": "error",
                "message": "'detailed_routes' fehlt in der Anfrage"
            }), 400
        
        detailed_routes = data['detailed_routes']

        # Umwandeln von Datumsfeldern (falls erforderlich)
        for route in detailed_routes:
            for abschnitt in route:
                # Konvertiere planned_departure_from und planned_arrival_to von String zu datetime
                if isinstance(abschnitt["planned_departure_from"], str):
                    abschnitt["planned_departure_from"] = datetime.fromisoformat(abschnitt["planned_departure_from"])
                if isinstance(abschnitt["planned_arrival_to"], str):
                    abschnitt["planned_arrival_to"] = datetime.fromisoformat(abschnitt["planned_arrival_to"])
                
                # planned_arrival_date_from in date konvertieren zu departure_date
                if "departure_date" in abschnitt and isinstance(abschnitt["departure_date"], str):
                    abschnitt["departure_date"] = datetime.fromisoformat(abschnitt["departure_date"]).date()

                # Sicherstellen, dass predicted_delay und umsteigezeit_minuten vorhanden sind
                if "predicted_delay" not in abschnitt or "umsteigezeit_minuten" not in abschnitt:
                    return jsonify({
                        "status": "error",
                        "message": "Felder 'predicted_delay' oder 'umsteigezeit_minuten' fehlen in einem Abschnitt"
                    }), 400

        # 🚀 Hauptlogik aufrufen
        analysed_routes = analyse_and_replan(detailed_routes, station_departures)

        # Antwort zurückgeben
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
    app.run(host="0.0.0.0", port=8007, debug=True)
