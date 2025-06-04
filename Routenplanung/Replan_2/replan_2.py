from datetime import datetime, timedelta
from routen_berechnung_2 import routenplanung, reconstruct_route_details, find_start_index, load_station_departures_pickle, save_station_departures_pickle, create_station_departures_from_db

def replan(abschnitt, route, station_departures):
    """
    Prüft, ob der Umstieg gefährdet ist, und plant ggf. eine Alternativroute.
    Gibt ein Ergebnis-Dictionary zurück oder None, falls kein Problem erkannt wurde.
    """
    umsteigeort = abschnitt.get("umsteigeort")
    umsteigezeit_minuten = abschnitt.get("umsteigezeit_minuten")
    predicted_delay = abschnitt.get("predicted_delay")

    if not (umsteigeort and umsteigezeit_minuten is not None and predicted_delay is not None):
        return None

    if umsteigezeit_minuten >= predicted_delay:
        return None  # Umstieg ist nicht gefährdet

    print(f"⚠️  Umstieg gefährdet bei {umsteigeort}!")

    neue_startzeit = abschnitt["planned_arrival_to"] + timedelta(minutes=predicted_delay)
    ziel = route[-1]["station_to"]
    travel_date = abschnitt["departure_date"]

    neue_routen = routenplanung(
        source=umsteigeort,
        target=ziel,
        station_departures=station_departures,
        departure_time=datetime.combine(travel_date, neue_startzeit.time()),
        travel_date=travel_date
    )

    if neue_routen:
        neue_route = neue_routen[0]
        neue_ankunftszeit = neue_route[-1]["planned_arrival_to"]
        alte_ankunftszeit = route[-1]["planned_arrival_to"]
        verspaetung_minuten = (neue_ankunftszeit - alte_ankunftszeit).total_seconds() / 60

        # Teilroute bis zum Umsteigeort (inklusive)
        index_umsteigeabschnitt = next((i for i, abschn in enumerate(route)
                                        if abschn["station_to"] == umsteigeort), None)
        if index_umsteigeabschnitt is not None:
            route_bis_umstieg = route[:index_umsteigeabschnitt + 1]
        else:
            route_bis_umstieg = []

        # Gesamte neue Route ab Umsteigeort anhängen
        komplette_alternative_route = route_bis_umstieg + neue_route

        return {
            "umsteigeort": umsteigeort,
            "neue_ankunftszeit": neue_ankunftszeit,
            "verspaetung_minuten": verspaetung_minuten,
            "alternative_route": komplette_alternative_route,
            "status": "ALTERNATIVE GEFUNDEN"
        }
    else:
        return {
            "umsteigeort": umsteigeort,
            "neue_ankunftszeit": None,
            "verspaetung_minuten": None,
            "alternative_route": None,
            "status": "KEINE VERBINDUNG GEFUNDEN"
        }

def berechne_gesamtverspaetungswahrscheinlichkeit(route):
    gesamt_wahrscheinlichkeit = 1.0

    for abschnitt in route:
        umsteigezeit_minuten = abschnitt.get("umsteigezeit_minuten")
        predicted_delay = abschnitt.get("predicted_delay")
        category_probabilities = abschnitt.get("category_probabilities")

        if umsteigezeit_minuten is not None and predicted_delay is not None:
            if category_probabilities:
                if umsteigezeit_minuten <= 10:
                    wahrscheinlichkeit = (
                        category_probabilities.get("On time", 0) +
                        category_probabilities.get("1-9 min", 0)
                    ) / 100
                elif umsteigezeit_minuten <= 20:
                    wahrscheinlichkeit = (
                        category_probabilities.get("On time", 0) +
                        category_probabilities.get("1-9 min", 0) +
                        category_probabilities.get("10-19 min", 0)
                    ) / 100
                elif umsteigezeit_minuten <= 30:
                    wahrscheinlichkeit = (
                        category_probabilities.get("On time", 0) +
                        category_probabilities.get("1-9 min", 0) +
                        category_probabilities.get("10-19 min", 0) +
                        category_probabilities.get("20-29 min", 0)
                    ) / 100
                else:
                    wahrscheinlichkeit = (
                        category_probabilities.get("On time", 0) +
                        category_probabilities.get("1-9 min", 0) +
                        category_probabilities.get("10-19 min", 0) +
                        category_probabilities.get("20-29 min", 0)
                    ) / 100

                gesamt_wahrscheinlichkeit *= wahrscheinlichkeit

    # Letzter Abschnitt separat behandeln
    letzter_abschnitt = route[-1]
    category_probabilities = letzter_abschnitt.get("category_probabilities")

    if category_probabilities:
        wahrscheinlichkeit_puenktlich = (
            category_probabilities.get("On time", 0) +
            category_probabilities.get("1-9 min", 0) +
            category_probabilities.get("10-19 min", 0)
        ) / 100
        gesamt_wahrscheinlichkeit *= wahrscheinlichkeit_puenktlich

    return round(gesamt_wahrscheinlichkeit * 100, 2)

def analyse_and_replan(detailed_routes, station_departures):
    neue_analyse = []

    for route in detailed_routes:
        neue_route_info = {
            "urspruengliche_route": route,
            "alternative_routeninfos": [],
            "erwartete_gesamtverspaetung_minuten": None,
            "gesamtverspaetungswahrscheinlichkeit": None
        }

        umstiegsgefahr_gefunden = False
        erste_verspaetung_gesetzt = False

        for abschnitt in route:
            replan_ergebnis = replan(abschnitt, route, station_departures)

            if replan_ergebnis:
                umstiegsgefahr_gefunden = True

                if replan_ergebnis["verspaetung_minuten"] is not None and not erste_verspaetung_gesetzt:
                    neue_route_info["erwartete_gesamtverspaetung_minuten"] = replan_ergebnis["verspaetung_minuten"]
                    erste_verspaetung_gesetzt = True

                neue_route_info["alternative_routeninfos"].append(replan_ergebnis)

        if not umstiegsgefahr_gefunden:
            letzter_abschnitt = route[-1]
            verspaetung = letzter_abschnitt.get("predicted_delay", 0)

            neue_route_info["alternative_routeninfos"].append({
                "status": "KEIN UMSTIEG GEFÄHRDET"
            })
            neue_route_info["erwartete_gesamtverspaetung_minuten"] = verspaetung

        neue_route_info["gesamtverspaetungswahrscheinlichkeit"] = berechne_gesamtverspaetungswahrscheinlichkeit(route)

        neue_analyse.append(neue_route_info)

    return neue_analyse


"""

detailed_routes = [[
    {
        "station_from": "Würzburg Hbf",
        "station_to": "Nürnberg Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 9, 3),
        "planned_arrival_to": datetime(2025, 4, 15, 9, 56),
        "train_number": 525.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": "Nürnberg Hbf",
        "umsteigezeit_minuten": 12,
        "predicted_delay": 10,
        "category_probabilities": {
            "On time": 20,
            "1-9 min": 60,
            "10-19 min": 15,
            "20-29 min": 4,
            "30+ min": 1
        }
    },
    {
        "station_from": "Nürnberg Hbf",
        "station_to": "Erlangen",
        "planned_departure_from": datetime(2025, 4, 15, 10, 8),
        "planned_arrival_to": datetime(2025, 4, 15, 10, 20),
        "train_number": 1710.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 0,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Erlangen",
        "station_to": "Erfurt Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 10, 22),
        "planned_arrival_to": datetime(2025, 4, 15, 11, 26),
        "train_number": 1710.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 0,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Erfurt Hbf",
        "station_to": "Leipzig Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 11, 28),
        "planned_arrival_to": datetime(2025, 4, 15, 12, 10),
        "train_number": 1710.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 0,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Leipzig Hbf",
        "station_to": "Lutherstadt Wittenberg Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 12, 16),
        "planned_arrival_to": datetime(2025, 4, 15, 12, 46),
        "train_number": 1710.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 10,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Lutherstadt Wittenberg Hbf",
        "station_to": "Berlin Südkreuz",
        "planned_departure_from": datetime(2025, 4, 15, 12, 48),
        "planned_arrival_to": datetime(2025, 4, 15, 13, 22),
        "train_number": 1710.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 0,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Berlin Südkreuz",
        "station_to": "Berlin Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 12, 48),
        "planned_arrival_to": datetime(2025, 4, 15, 13, 29),
        "train_number": 1710.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 10,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    }
],
[
    {
        "station_from": "Hannover Hbf",
        "station_to": "Wolfsburg Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 12, 31),
        "planned_arrival_to": datetime(2025, 4, 15, 13, 3),
        "train_number": 857.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 8,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Wolfsburg Hbf",
        "station_to": "Berlin-Spandau",
        "planned_departure_from": datetime(2025, 4, 15, 13, 5),
        "planned_arrival_to": datetime(2025, 4, 15, 13, 58),
        "train_number": 857.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 14,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Berlin-Spandau",
        "station_to": "Berlin Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 14, 0),
        "planned_arrival_to": datetime(2025, 4, 15, 14, 16),
        "train_number": 857.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": "Berlin Hbf",
        "umsteigezeit_minuten": 11,
        "predicted_delay": 12,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Berlin Hbf",
        "station_to": "Berlin Südkreuz",
        "planned_departure_from": datetime(2025, 4, 15, 14, 27),
        "planned_arrival_to": datetime(2025, 4, 15, 14, 33),
        "train_number": 1601.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 3,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Berlin Südkreuz",
        "station_to": "Lutherstadt Wittenberg Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 14, 36),
        "planned_arrival_to": datetime(2025, 4, 15, 15, 10),
        "train_number": 1601.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 2,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Lutherstadt Wittenberg Hbf",
        "station_to": "Leipzig Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 15, 11),
        "planned_arrival_to": datetime(2025, 4, 15, 15, 42),
        "train_number": 1601.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 4,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Leipzig Hbf",
        "station_to": "Erfurt Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 15, 48),
        "planned_arrival_to": datetime(2025, 4, 15, 16, 29),
        "train_number": 1601.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": "Erfurt Hbf",
        "umsteigezeit_minuten": 3,
        "predicted_delay": 7,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    },
    {
        "station_from": "Erfurt Hbf",
        "station_to": "Erlangen",
        "planned_departure_from": datetime(2025, 4, 15, 16, 36),
        "planned_arrival_to": datetime(2025, 4, 15, 17, 36),
        "train_number": 1601.0,
        "departure_date": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "predicted_delay": 5,
        "category_probabilities": {
            "On time": 10,
            "1-9 min": 15,
            "10-19 min": 55,
            "20-29 min": 15,
            "30+ min": 5
        }
    }
]
]

# Versuche Pickle-Datei zu laden
station_departures = load_station_departures_pickle()

# Falls keine Pickle-Datei vorhanden ist, neu erstellen und speichern
if station_departures is None:
    station_departures = create_station_departures_from_db()
    print("✅ station_departures erstellt!")
    save_station_departures_pickle(station_departures)


    # 📅 Datum und Uhrzeit für Abfahrt
#travel_date = datetime.strptime("2025-04-15", "%Y-%m-%d").date()
   


# Test: analyse_and_replan aufrufen
neue_analyse = analyse_and_replan(detailed_routes, station_departures)

# Ergebnisse ausgeben
print("\n📋 Ergebnisse der neuen Analyse:")
for idx, eintrag in enumerate(neue_analyse, 1):
    print(f"\n🚆 Route {idx}:")
    for key, value in eintrag.items():
        if isinstance(value, list):
            print(f"  {key}:")
            for item in value:
                print(f"    - {item}")
        else:
            print(f"  {key}: {value}")


#gesamt_wahrscheinlichkeit = berechne_gesamtverspaetungswahrscheinlichkeit(detailed_routes[0])
#print(gesamt_wahrscheinlichkeit)
"""
