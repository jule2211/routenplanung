from flask import Flask, request, jsonify
from datetime import datetime
import pickle
from routen_berechnung import routenplanung
from replan import analyse_and_replan  

app = Flask(__name__)


with open("station_departure.pkl", "rb") as f:
    station_departures = pickle.load(f)
print("station_departures geladen")


@app.route("/", methods=["GET"])
def hello():
    return "API läuft"


@app.route("/route", methods=["GET"])
def route():
    try:
        source = request.args.get("source")
        target = request.args.get("target")
        date = request.args.get("date")
        time = request.args.get("time")

        if not all([source, target, date, time]):
            return jsonify({"error": "Missing required parameters: source, target, date, time"}), 400

        try:
            travel_date = datetime.strptime(date, "%Y-%m-%d").date()
            departure_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except ValueError as e:
            return jsonify({"error": f"Invalid date or time format: {str(e)}"}), 400

        routes = routenplanung(
            source=source,
            target=target,
            station_departures=station_departures,
            departure_time=departure_time,
            travel_date=travel_date
        )

        if not routes:
            return jsonify({"error": "No routes found."}), 404

        return jsonify(routes)
    except Exception as e:
        print(f"Error in /route: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyse_and_replan", methods=["POST"])
def api_analyse_and_replan():
    try:
        data = request.get_json()

        
        if 'detailed_routes' not in data:
            return jsonify({
                "status": "error",
                "message": "'detailed_routes' fehlt in der Anfrage"
            }), 400
        
        detailed_routes = data['detailed_routes']

        
        for route in detailed_routes:
            for abschnitt in route:
                if isinstance(abschnitt["planned_departure_from"], str):
                    abschnitt["planned_departure_from"] = datetime.fromisoformat(abschnitt["planned_departure_from"])
                if isinstance(abschnitt["planned_arrival_to"], str):
                    abschnitt["planned_arrival_to"] = datetime.fromisoformat(abschnitt["planned_arrival_to"])
                if "departure_date" in abschnitt and isinstance(abschnitt["departure_date"], str):
                    abschnitt["departure_date"] = datetime.fromisoformat(abschnitt["departure_date"]).date()
                
                if "predicted_delay" not in abschnitt or "umsteigezeit_minuten" not in abschnitt:
                    return jsonify({
                        "status": "error",
                        "message": "Felder 'predicted_delay' oder 'umsteigezeit_minuten' fehlen in einem Abschnitt"
                    }), 400

       
        analysed_routes = analyse_and_replan(detailed_routes, station_departures)

        return jsonify({
            "status": "success",
            "analysed_routes": analysed_routes
        }), 200

    except Exception as e:
        print(f"❌ Fehler in /api/analyse_and_replan: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)
