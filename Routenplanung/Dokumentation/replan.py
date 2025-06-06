from datetime import datetime, timedelta
from routen_berechnung_2 import routenplanung, reconstruct_route_details, find_start_index, load_station_departures_pickle, save_station_departures_pickle, create_station_departures_from_db

def replan(abschnitt, route, station_departures):
    """
    Prüft, ob der Umstieg gefährdet ist, und plant ggf. eine Alternativroute.
    Gibt ein Ergebnis-Dictionary zurück oder None, falls kein Problem erkannt wurde.
    """

    # Prüfung der Eingabedaten
    umsteigeort = abschnitt.get("umsteigeort")
    umsteigezeit_minuten = abschnitt.get("umsteigezeit_minuten")
    predicted_delay = abschnitt.get("predicted_delay")

    if not (umsteigeort and umsteigezeit_minuten is not None and predicted_delay is not None):
        return None

    if umsteigezeit_minuten >= predicted_delay:
        return None  # Umstieg ist nicht gefährdet

    
    # Verspätung gefährdet den Umstieg – alternative Route muss geplant werden
    neue_startzeit = abschnitt["planned_arrival_to"] + timedelta(minutes=predicted_delay)
    ziel = route[-1]["station_to"]
    travel_date = abschnitt["departure_date"]

    # Routenplaner wird aufgerufen
    neue_routen = routenplanung(
        source=umsteigeort,
        target=ziel,
        station_departures=station_departures,
        departure_time=datetime.combine(travel_date, neue_startzeit.time()),
        travel_date=travel_date
    )

    # Wenn eine alternative Route gefunden wurde: Verspätung berechnen
    if neue_routen:
        neue_route = neue_routen[0]
        neue_ankunftszeit = neue_route[-1]["planned_arrival_to"]
        alte_ankunftszeit = route[-1]["planned_arrival_to"]
        verspaetung_minuten = (neue_ankunftszeit - alte_ankunftszeit).total_seconds() / 60

        # Teilroute bis zum Umsteigeort wird beibehalten
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
    """
    Schätzt die Wahrscheinlichkeit, dass eine Route pünktlich ankommt.
    Basierend auf den Umsteigezeiten und den kategorisierten Verspätungswahrscheinlichkeiten.
    """
    gesamt_wahrscheinlichkeit = 1.0

    # Multiplikation der Wahrscheinlichkeiten aller Abschnitte die zur Gesamtverspätungwahrscheinlichkeit beitragen:
    for abschnitt in route:
        umsteigezeit_minuten = abschnitt.get("umsteigezeit_minuten")
        predicted_delay = abschnitt.get("predicted_delay")
        category_probabilities = abschnitt.get("category_probabilities")

        # Wahrscheinlichkeiten der Umstieg nicht zu schaffen (Näherung)
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

    # Wahrscheinlichkeit im letzten Abschnitt der Route verspätet zu sein
    letzter_abschnitt = route[-1]
    category_probabilities = letzter_abschnitt.get("category_probabilities")

    if category_probabilities:
        wahrscheinlichkeit_puenktlich = (
            category_probabilities.get("On time", 0) +
            category_probabilities.get("1-9 min", 0) +
            category_probabilities.get("10-19 min", 0)
        ) / 100

        # Gesamtwahrscheinlichkeit multiplizieren
        gesamt_wahrscheinlichkeit *= wahrscheinlichkeit_puenktlich

    return round(gesamt_wahrscheinlichkeit * 100, 2)




def analyse_and_replan(detailed_routes, station_departures):
    """
    Analysiert mehrere Verbindungen auf gefährdete Umstiege.
    Führt bei Bedarf Neuplanungen durch und berechnet Verspätungswahrscheinlichkeiten.
    Gibt eine Liste von Analyseergebnissen zurück.
    """

    # Vorbereitung Ergebnisliste
    neue_analyse = []

    #Schleife über alle Routen
    for route in detailed_routes:
        neue_route_info = {
            "urspruengliche_route": route,
            "alternative_routeninfos": [],
            "erwartete_gesamtverspaetung_minuten": None,
            "gesamtverspaetungswahrscheinlichkeit": None
        }

        umstiegsgefahr_gefunden = False
        erste_verspaetung_gesetzt = False

        # Einzelne Abschnitte auf Gefährdung eines Umstiegs analysieren und gegebenenfalls dadurch erwartete verspätung berechnen
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

        # Gesamtverspätungswahrscheinlichkeit der Route berechnen
        neue_route_info["gesamtverspaetungswahrscheinlichkeit"] = berechne_gesamtverspaetungswahrscheinlichkeit(route)

        neue_analyse.append(neue_route_info)

    return neue_analyse


