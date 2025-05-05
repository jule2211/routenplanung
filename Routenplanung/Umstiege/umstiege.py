from datetime import datetime, timedelta
from routenberechnung_mit_umstiegen import routenplanung, reconstruct_route_details, find_start_index, load_station_departures_pickle, save_station_departures_pickle, create_station_departures_from_db


def analyse_and_replan(detailed_routes, station_departures):
    neue_analyse = []

    for route in detailed_routes:
        neue_route_info = {
            "urspruengliche_route": route,
            "alternative_routeninfos": []
        }

        for idx, abschnitt in enumerate(route):
            umsteigeort = abschnitt.get("umsteigeort")
            umsteigezeit_minuten = abschnitt.get("umsteigezeit_minuten")
            voraussichtliche_verspaetung = abschnitt.get("voraussichtliche_verspaetung")

            # Prüfen ob ein Umstieg existiert und gefährdet ist
            if umsteigeort and umsteigezeit_minuten is not None and voraussichtliche_verspaetung is not None:
                if umsteigezeit_minuten < voraussichtliche_verspaetung:
                    print(f"⚠️  Umstieg gefährdet bei {umsteigeort}!")

                    # Neue Startzeit berechnen (geplante Ankunft + Verspätung)
                    neue_startzeit = abschnitt["planned_arrival_to"] + timedelta(minutes=voraussichtliche_verspaetung)
                    print(f"Neue Startzeit für Routenplanung: {neue_startzeit}")

                    ziel = route[-1]["station_name_to"]  # Ziel bleibt gleich wie in der Originalroute

                    # 🛠 travel_date wird jetzt aus dem Abschnitt entnommen!
                    travel_date = abschnitt["planned_arrival_date_from"]

                    neue_routen = routenplanung(
                        source=umsteigeort,
                        target=ziel,
                        station_departures=station_departures,
                        departure_time=datetime.combine(travel_date, neue_startzeit.time()),
                        travel_date=travel_date
                    )

                    if neue_routen:
                        neue_route = neue_routen[0]  # Nimm die erste gefundene Route
                        neue_ankunftszeit = neue_route[-1]["planned_arrival_to"]
                        alte_ankunftszeit = route[-1]["planned_arrival_to"]
                        verspaetung_minuten = (neue_ankunftszeit - alte_ankunftszeit).total_seconds() / 60

                        neue_route_info["alternative_routeninfos"].append({
                            "umsteigeort": umsteigeort,
                            "neue_ankunftszeit": neue_ankunftszeit,
                            "verspaetung_minuten": verspaetung_minuten,
                            "genutzte_zuege": list(set(abschnitt["train_number"] for abschnitt in neue_route))

                        })
                    else:
                        neue_route_info["alternative_routeninfos"].append({
                            "umsteigeort": umsteigeort,
                            "neue_ankunftszeit": None,
                            "verspaetung_minuten": None,
                            "genutzte_zuege": [],
                            "status": "KEINE VERBINDUNG GEFUNDEN"
                        })

        neue_analyse.append(neue_route_info)

    return neue_analyse


"""


# Test-Daten für detailed_routes
detailed_routes = [[
    {
        "station_name_from": "Würzburg Hbf",
        "station_name_to": "Nürnberg Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 9, 3),
        "planned_arrival_to": datetime(2025, 4, 15, 9, 56),
        "train_number": 525.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": "Nürnberg Hbf",   # <-- Umstieg HIER eingetragen
        "umsteigezeit_minuten": 12,
        "voraussichtliche_verspaetung": 15  # Hypothetisch 15 Minuten Verspätung => Umstieg gefährdet!
    },
    {
        "station_name_from": "Nürnberg Hbf",
        "station_name_to": "Erlangen",
        "planned_departure_from": datetime(2025, 4, 15, 10, 8),
        "planned_arrival_to": datetime(2025, 4, 15, 10, 20),
        "train_number": 1710.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,  # <-- Kein Umstieg hier
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 0  # Dieser Abschnitt ist planmäßig
    },
    {
        "station_name_from": "Erlangen",
        "station_name_to": "Erfurt Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 10, 22),
        "planned_arrival_to": datetime(2025, 4, 15, 11, 26),
        "train_number": 1710.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 0
    },
    {
        "station_name_from": "Erfurt Hbf",
        "station_name_to": "Leipzig Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 11, 28),
        "planned_arrival_to": datetime(2025, 4, 15, 12, 10),
        "train_number": 1710.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 0
    },
    {
        "station_name_from": "Leipzig Hbf",
        "station_name_to": "Lutherstadt Wittenberg Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 12, 16),
        "planned_arrival_to": datetime(2025, 4, 15, 12, 46),
        "train_number": 1710.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 0
    },
    {
        "station_name_from": "Lutherstadt Wittenberg Hbf",
        "station_name_to": "Berlin Südkreuz",
        "planned_departure_from": datetime(2025, 4, 15, 12, 48),
        "planned_arrival_to": datetime(2025, 4, 15, 13, 22),
        "train_number": 1710.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 0
    },
    {
        "station_name_from": "Berlin Südkreuz",
        "station_name_to": "Berlin Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 12, 48),
        "planned_arrival_to": datetime(2025, 4, 15, 13, 29),
        "train_number": 1710.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 0
    }
],
[
    {
        "station_name_from": "Hannover Hbf",
        "station_name_to": "Wolfsburg Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 12, 31),
        "planned_arrival_to": datetime(2025, 4, 15, 13, 3),
        "train_number": 857.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 8
    },
    {
        "station_name_from": "Wolfsburg Hbf",
        "station_name_to": "Berlin-Spandau",
        "planned_departure_from": datetime(2025, 4, 15, 13, 5),
        "planned_arrival_to": datetime(2025, 4, 15, 13, 58),
        "train_number": 857.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 14
    },
    {
        "station_name_from": "Berlin-Spandau",
        "station_name_to": "Berlin Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 14, 0),
        "planned_arrival_to": datetime(2025, 4, 15, 14, 16),
        "train_number": 857.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": "Berlin Hbf",
        "umsteigezeit_minuten": 11,
        "voraussichtliche_verspaetung": 12
    },
    {
        "station_name_from": "Berlin Hbf",
        "station_name_to": "Berlin Südkreuz",
        "planned_departure_from": datetime(2025, 4, 15, 14, 27),
        "planned_arrival_to": datetime(2025, 4, 15, 14, 33),
        "train_number": 1601.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 3
    },
    {
        "station_name_from": "Berlin Südkreuz",
        "station_name_to": "Lutherstadt Wittenberg Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 14, 36),
        "planned_arrival_to": datetime(2025, 4, 15, 15, 10),
        "train_number": 1601.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 2
    },
    {
        "station_name_from": "Lutherstadt Wittenberg Hbf",
        "station_name_to": "Leipzig Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 15, 11),
        "planned_arrival_to": datetime(2025, 4, 15, 15, 42),
        "train_number": 1601.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 4
    },
    {
        "station_name_from": "Leipzig Hbf",
        "station_name_to": "Erfurt Hbf",
        "planned_departure_from": datetime(2025, 4, 15, 15, 48),
        "planned_arrival_to": datetime(2025, 4, 15, 16, 29),
        "train_number": 1601.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": "Erfurt Hbf",
        "umsteigezeit_minuten": 3,
        "voraussichtliche_verspaetung": 7
    },
    {
        "station_name_from": "Erfurt Hbf",
        "station_name_to": "Erlangen",
        "planned_departure_from": datetime(2025, 4, 15, 16, 36),
        "planned_arrival_to": datetime(2025, 4, 15, 17, 36),
        "train_number": 1601.0,
        "planned_arrival_date_from": datetime(2025, 4, 15).date(),
        "zugtyp": "ICE",
        "umsteigeort": None,
        "umsteigezeit_minuten": None,
        "voraussichtliche_verspaetung": 5
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

"""
