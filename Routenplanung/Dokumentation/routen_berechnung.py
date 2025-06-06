import pandas as pd
import heapq
from datetime import datetime, timedelta
import pickle
import os
import bisect  
from collections import defaultdict, Counter
import time
import psycopg2
from pprint import pprint

"""
erstellt ein Dictionary namens station_departures, in dem für jeden Bahnhof alle bekannten Abfahrten 
(basierend auf dem geplanten Fahrplan in der Datenbank) gelistet sind. 
"""

def create_station_departures_from_db():
    connection = psycopg2.connect(
        host="35.246.149.161",
        port=5432,
        dbname="postgres",
        user="postgres",
        password="UWP12345!"
    )

    # SQL-Abfrage: Ruft Zugverbindungsdaten sortiert nach Zugnummer und Haltestellenreihenfolge ab
    query = """
        SELECT zug AS train_number, halt AS station_name, abfahrt_geplant AS planned_departure,
               ankunft_geplant AS planned_arrival, halt_nummer AS reihenfolge,
               zugtyp, train_avg_30, station_avg_30
        FROM sollfahrplan_reihenfolge
        ORDER BY zug, halt_nummer;
    """

    # Ausführen der Abfrage und Laden in ein Pandas DataFrame
    df = pd.read_sql(query, connection)
    connection.close()

    # Umwandlung von Zeit-Strings in `datetime.time`-Objekte (z.B. "14:25:00" → `datetime.time`)
    df["planned_departure"] = pd.to_datetime(df["planned_departure"], format="%H:%M:%S", errors="coerce").dt.time
    df["planned_arrival"] = pd.to_datetime(df["planned_arrival"], format="%H:%M:%S", errors="coerce").dt.time

    # Sortieren nach Zug und Reihenfolge
    df.sort_values(by=["train_number", "reihenfolge"], inplace=True)

    # Für jede Zeile die nächste Station und geplante Ankunftszeit dieser Station berechnen
    df["next_station"] = df.groupby("train_number")["station_name"].shift(-1)
    df["next_arrival"] = df.groupby("train_number")["planned_arrival"].shift(-1)

    # Dictionary, das für jeden Bahnhof eine Liste von Abfahrten speichert
    station_departures = defaultdict(list)

    # Heutiges Datum als Basis (damit Zeitangaben zu datetime kombiniert werden können)
    base_date = datetime.today().date()


    # Iteration über jede Zeile des DataFrames
    for _, row in df.iterrows():

        # Informationen für die Routenplanung
        train = row["train_number"]
        from_station = row["station_name"]
        to_station = row["next_station"]
        dep_time = row["planned_departure"]
        arr_time = row["next_arrival"]
        zugtyp = row["zugtyp"]

        # Informationen für die Vorhersage
        halt_nummer = row["reihenfolge"] if pd.notna(row["reihenfolge"]) else None
        train_avg_30 = row["train_avg_30"]
        station_avg_30 = row["station_avg_30"]

        # Ungültige Daten überspringen
        if pd.isna(dep_time) or pd.isna(arr_time) or pd.isna(to_station):
            continue

        dep_dt = datetime.combine(base_date, dep_time)
        arr_dt = datetime.combine(base_date, arr_time)

        # Eintrag in das Dictionary für die Abfahrtsstation
        station_departures[from_station].append((
            train, to_station, dep_dt, arr_dt,
            zugtyp, halt_nummer, train_avg_30, station_avg_30
        ))

    # Sortierung der Verbindungen pro Abfahrtsbahnhof nach Abfahrtszeit
    for connections in station_departures.values():
        connections.sort(key=lambda x: x[2]) 

    return dict(station_departures)


"""
erstellt ein Dictionary namens updated_station_departures, 
in welchem die geplante Zeit um die entsprechende voraussichtliche Verspätung korrigiert wird, 
sodass man eine neue, "realistischere" Fahrplandatenstruktur erhält
"""

def apply_delays_to_station_departures(station_departures, delays):

    # Initialisiert ein neues Dictionary für aktualisierte Verbindungen nach Verspätung
    updated_station_departures = defaultdict(list)


    # Iteriert über alle Abfahrtsstationen und ihre Verbindungen
    for from_station, connections in station_departures.items():
        for connection in connections:
            (
                train_number, to_station, dep_dt, arr_dt,
                zugtyp, halt_nummer, train_avg_30, station_avg_30
            ) = connection


            # Schlüssel zur Identifikation der Verbindung für die Verspätungsdaten
            key = (from_station, to_station, train_number)

            # Hole Verspätungen aus dem Dictionary oder setze sie auf 0, falls nicht vorhanden
            dep_delay, arr_delay = delays.get(key, (0, 0)) 

            # Berechne neue Abfahrts- und Ankunftszeiten mit Verspätung
            new_dep_dt = dep_dt + timedelta(minutes=dep_delay)
            new_arr_dt = arr_dt + timedelta(minutes=arr_delay)

            # Füge die aktualisierte Verbindung dem neuen Dictionary hinzu
            updated_station_departures[from_station].append((
                train_number, to_station, new_dep_dt, new_arr_dt,
                zugtyp, halt_nummer, train_avg_30, station_avg_30
            ))

        # Sortiere alle Verbindungen einer Station nach der neuen Abfahrtszeit
        updated_station_departures[from_station].sort(key=lambda x: x[2])

    return dict(updated_station_departures)

# lädt ein gespeichertes station_departures-Dictionary aus einer Pickle-Datei
def load_station_departures_pickle(filename="station_departure_2.pkl"):
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            data = pickle.load(f)
            if isinstance(data, dict) and data:
                return data
            else:
                print(" Keine Pickle-Datei gefunden")
    return None  

# speichert ein übergebenes station_departures-Dictionary als Pickle-Datei
def save_station_departures_pickle(data, filename="station_departure_2.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(data, f)
    print(f" station_departures wurde als Pickle-Datei gespeichert: {filename}")

# findet den Index der ersten Verbindung, deren Abfahrtszeit gleich oder nach der angegebenen Ankunftszeit liegt.
def find_start_index(connections, arrival_time_only):
    for idx, conn in enumerate(connections):
        train, next_station, dep_time, arr_time, zugtyp, halt_nummer, train_avg_30, station_avg_30 = conn

        if isinstance(dep_time, datetime):
            dep_time_only = dep_time.time()
        else:
            dep_time_only = dep_time

        # Wenn Abfahrtszeit nach (>=) Ankunftszeit liegt, nehmen wir diese Verbindung
        if dep_time_only >= arrival_time_only:
            return idx

    # Wenn keine spätere Abfahrt gefunden wird ➔ ab Index 0 neu prüfen (nächster Tag)
    return 0

def reconstruct_route_details(previous_stop, previous_train, arrival_states, source, target_key, station_departures, travel_date, prediction_information):
    
    # Initialisiere leere Routeliste
    route = []

    # Entpacke Zielknoten: Bahnhof, Ankunftszeit, Zugnummer
    station, arrival_time, train = target_key

     # Set zur Erkennung von Zyklen
    visited = set()

    # Wird für die Weitergabe der Abfahrtszeit an den nächsten Abschnitt genutzt
    next_dep_time = None

    # Info zu einem eventuell notwendigen Umstieg
    pending_transfer_info = None

    # Zählt Schritte zur Nachverfolgung
    step = 0

    # Führe die Schleife aus, bis wir keinen Vorgänger mehr haben
    while (station, arrival_time, train) in previous_stop:
        step += 1

        # Zyklische Referenzen abfangen – sollte nicht vorkommen
        if (station, arrival_time, train) in visited:
            return None
        visited.add((station, arrival_time, train))

        # Hole Vorgängerstation und Vorgängerzug aus vorherigen Dictionaries
        prev_station = previous_stop[(station, arrival_time, train)]
        prev_train = previous_train.get((station, arrival_time, train), None)

        dep_time = None
        arrival_time_prev = None

        # Lade mögliche Ankünfte an der Vorgängerstation
        arrival_list = arrival_states.get(prev_station, [])
        
        # Suche passende Verbindung mit dem richtigen Zug
        for (t_arrival, t_departure, transfers, tr) in arrival_list:
            if tr == prev_train and t_arrival <= arrival_time:
                dep_time = t_departure
                arrival_time_prev = t_arrival
                break

        # Abbruch, wenn keine passende Verbindung gefunden wurde
        if dep_time is None:
            break

        # Bestimme die Abfahrtszeit an der aktuellen Station
        if next_dep_time is not None:
            departure_used = next_dep_time
        else:
            departure_used = None
            for (arrival, departure, transfers, tr) in arrival_states.get(station, []):
                if tr == train:
                    departure_used = departure
                    break

        # Lade Zusatzinformationen zur Prognose
        pred_info = prediction_information.get((prev_station, station, train), {})
        zugtyp = pred_info.get("zugtyp")
        halt_nummer = pred_info.get("halt_nummer")
        train_avg_30 = pred_info.get("train_avg_30")
        station_avg_30 = pred_info.get("station_avg_30")

        # Falls vorher ein Umstieg gemerkt wurde, hole Infos
        umsteigeort = None
        umsteigezeit_minuten = None
        if pending_transfer_info:
            umsteigeort, umsteigezeit_minuten = pending_transfer_info
            pending_transfer_info = None  # Reset für nächsten Abschnitt

        # Baue einen Routeneintrag aus allen gesammelten Infos
        route_entry = {
            "station_name_from": prev_station,
            "station_name_to": station,
            "planned_departure_from": departure_used,
            "planned_arrival_to": arrival_time,
            "train_number": train,
            "planned_arrival_date_from": departure_used.date(),
            "zugtyp": zugtyp,
            "halt_nummer": halt_nummer,
            "train_avg_30": train_avg_30,
            "station_avg_30": station_avg_30,
            "umsteigeort": umsteigeort,
            "umsteigezeit_minuten": umsteigezeit_minuten
        }
        
        # Füge den Eintrag zur Route hinzu
        route.append(route_entry)

        # Falls ein Zugwechsel stattgefunden hat, berechne Umsteigezeit und merke sie
        if (train != prev_train) and (prev_train is not None):
            umsteigezeit_minuten_jetzt = (departure_used - arrival_time_prev).total_seconds() / 60
            pending_transfer_info = (prev_station, umsteigezeit_minuten_jetzt)


        # Vorbereitung für nächsten Loop-Durchlauf
        station = prev_station
        train = prev_train
        arrival_time = arrival_time_prev
        next_dep_time = dep_time

    # Route wurde rückwärts aufgebaut, daher umdrehen
    route.reverse()

    return route




# Berechnet (bis zu) vier optimale Zugverbindungen von einem Start- zu einem Zielbahnhof
def routenplanung(source, target, station_departures, departure_time, buffer_minutes=600, min_transfer_minutes=5,  
                  max_initial_wait_hours=6, max_transfer_wait_hours=2, travel_date=None,
                  max_attempts=5, delay_hours=2, max_duration_seconds = 5, delays = None):

    # (1) Initialisierung und Vorbereitung

    start_time_total = time.time() # Gesamtstartzeit zur Laufzeitmessung
    deadline_time = start_time_total + max_duration_seconds # Abbruchzeitpunkt für den Algorithmus

    # Falls kein konkretes Reisedatum angegeben ist, verwende das heutige Datum
    if travel_date is None:
        travel_date = datetime.today().date()

    min_transfer_time = timedelta(minutes=min_transfer_minutes)

    # Datenstrukturen
    previous_stop = {} # Speichert für jeden Zustand (Bahnhof, Zeit, Zug) den vorherigen Halt
    previous_train = {} # Speichert den Zug vor dem aktuellen Abschnitt
    arrival_info = defaultdict(lambda: (datetime.max, float("inf"))) # Für jeden Bahnhof: Beste bekannte Ankunftszeit + Anzahl Umstiege
    arrival_states = defaultdict(list) # Liste aller bekannten Zustände pro Bahnhof
    prediction_information = {} # Zusätzliche Infos zu genutzten Verbindungen ( für Verspätungsprognosen)
    first_train_used = {} # Speichert für jeden Route den ersten genutzten Zug
    all_target_routes = set() # Speichert alle gültigen Routen zum Zielbahnhof

    verbindung_counter = 0 # Zählt die untersuchten Verbindungen (für Analyse/Debugging)
    iteration_count = 0 # Zählt die Schritte der Hauptschleife

    current_departure_time = departure_time # Startzeit für ersten Durchlauf

    # # Falls Verspätungsdaten angegeben sind, wende diese auf die Abfahrtsdaten an
    if delays is not None:
        station_departures = apply_delays_to_station_departures(station_departures, delays)




    # (2) Methode zum filtern / auswählen geeigneter Routen

    # Wählt aus allen gefundenen Routen die besten Verbindungen unter Berücksichtigung von Umstiegen und Ankunftszeit aus
    def filter_and_sort_routes(all_routes_set):

        # Dictionary, um für jede Route mit gleichem Ziel, Ankunftszeit und Startzug
        # nur die Route mit der geringsten Anzahl an Umstiegen zu behalten
        best_routes_map = {}
        for (station, arrival_time, train), transfers in all_routes_set:

            # Ermittle den ersten Zug der Route
            first_train = first_train_used.get((station, arrival_time, train), "?")
            key = (station, arrival_time, first_train)

             # Speichere Route nur, wenn sie besser (weniger Umstiege) ist als die bisher gespeicherte
            if key not in best_routes_map or transfers < best_routes_map[key][1]:
                best_routes_map[key] = ((station, arrival_time, train), transfers)

        time_window_minutes = 45  # Zeitfenster für vergleichbare Ankünfte

        # Gruppiere alle besten Routen nach dem jeweils ersten Zug
        routes_by_start_train = defaultdict(list)
        for (station, arrival_time, first_train), (route_info, transfers) in best_routes_map.items():
            routes_by_start_train[first_train].append((station, arrival_time, route_info, transfers))

        filtered = []

        # Pro Startzug wähle eine Route mit bester Ankunftszeit und geringsten Umstiegen
        for first_train, routes in routes_by_start_train.items():

            # Sortiere nach Ankunftszeit
            routes.sort(key=lambda x: x[1])
            best_station, best_arrival_time, best_route_info, best_transfers = routes[0]

            # Beste Route immer behalten
            filtered.append((best_route_info, best_transfers))
            for station, arrival_time, route_info, transfers in routes[1:]:
                delta_minutes = (arrival_time - best_arrival_time).total_seconds() / 60

                # Weitere Routen nur behalten, wenn sie nah (innerhalb time_window_minutes) an der besten liegen 
                # oder weniger Umstiege haben
                if delta_minutes <= time_window_minutes and transfers <= best_transfers:
                    filtered.append((route_info, transfers))
                elif delta_minutes > time_window_minutes and transfers < best_transfers:
                    filtered.append((route_info, transfers))

        # Gib die gefilterten Routen zurück, sortiert nach Ankunftszeit
        return sorted(filtered, key=lambda x: x[0][1])
    



    # (3) Methode zur eigentlichen Routenberechnung

    # Der eigentliche Routing-Algorithmus. Nutzt eine Priority Queue (heap) zur Routenberechnung.
    def verarbeite_verbindungen(current_departure_time, start_idx_override=None):

        # Zugriff auf die äußeren Zählvariablen
        nonlocal verbindung_counter, iteration_count

        # Initialisierung der lokalen Prioritätswarteschlange
        # Enthält Tupel: (Ankunftszeit, aktueller Bahnhof, aktueller Zug, Anzahl Umstiege)
        queue_local = [(current_departure_time, source, None, 0)]
        heapq.heapify(queue_local)

        # Hauptschleife: Solange noch Zustände in der Warteschlange sind
        while queue_local:
            # Hole Zustand mit frühester Ankunftszeit
            arrival_time, current_stop, current_train, transfers = heapq.heappop(queue_local)
            iteration_count += 1

            # Wenn Ziel erreicht, Route merken und keine weiteren Verbindungen von hier prüfen
            if current_stop == target:
                all_target_routes.add(((current_stop, arrival_time, current_train), transfers))
                continue

            # Wenn es vom aktuellen Bahnhof keine Verbindungen gibt, überspringen
            if current_stop not in station_departures:
                continue

            connections = station_departures[current_stop]

            # Extrahiere Uhrzeit aus Ankunftszeit (falls datetime-Objekt)
            arrival_time_only = arrival_time.time() if isinstance(arrival_time, datetime) else arrival_time

            # Bestimme Startindex in der Verbindungs-Liste (optional: Override nutzen)
            if start_idx_override is not None:
                start_idx = start_idx_override
            else:
                start_idx = find_start_index(connections, arrival_time_only)

            # Schleife über alle möglichen Verbindungen ab dem berechneten Index
            for i in range(start_idx, len(connections)):
                verbindung_counter += 1

                # Entpacke Verbindungsdetails
                (train, next_station, dep_time, arr_time, zugtyp, halt_nummer, train_avg_30, station_avg_30) = connections[i]

                dep_time = dep_time.time() if isinstance(dep_time, datetime) else dep_time
                arr_time = arr_time.time() if isinstance(arr_time, datetime) else arr_time

                # Kombiniere Uhrzeit mit Reisedatum zu datetime-Objekten
                planned_departure_time = datetime.combine(travel_date, dep_time)
                planned_arrival_time = datetime.combine(travel_date, arr_time)

                # Korrektur, wenn Ankunft nach Mitternacht erfolgt (Tageswechsel)
                if planned_arrival_time <= planned_departure_time:
                    planned_arrival_time += timedelta(days=1)

                # Folgeverbindungen müssen entsprechend verschoben werden, um zeitlich konsistente Routen zu ermöglichen
                while planned_departure_time < arrival_time:
                    planned_departure_time += timedelta(days=1)
                    planned_arrival_time += timedelta(days=1)

                # Bestimme zulässige maximale Wartezeit (abhängig davon, ob Start oder Umstieg)    
                wartezeit = (planned_departure_time - arrival_time).total_seconds() / 3600
                max_wait = max_initial_wait_hours if current_train is None else max_transfer_wait_hours

                # Wenn Wartezeit zu lang, Verbindung überspringen
                if wartezeit > max_wait:
                    continue

                # Prüfe, ob ein Umstieg stattfindet
                new_transfers = transfers
                if current_train is not None and train != current_train:
                    new_transfers += 1

                    # Wenn Umstiegszeit zu kurz ist, Verbindung überspringen
                    if (planned_departure_time - arrival_time) < min_transfer_time:
                        continue

                 # Hole bisher beste bekannte Ankunftszeit und Umstiege für den Bahnhof
                best_time, best_transfers = arrival_info[next_station]

                # Prüfe, ob diese Verbindung besser ist:
                # - frühere Ankunft oder
                # - gleiche Ankunft, aber weniger Umstiege
                is_better = (
                    planned_arrival_time < best_time or
                    (planned_arrival_time == best_time and new_transfers < best_transfers)
                )

                # Oder ob sie sich zumindest innerhalb des Toleranz-Puffers befindet
                within_buffer = (
                    best_time != datetime.max and
                    planned_arrival_time < (best_time + timedelta(minutes=buffer_minutes)) and
                    new_transfers <= best_transfers 
                )

                # Falls Verbindung gut genug ist, speichern und weiterverfolgen
                if (is_better or within_buffer):

                    # Speichere neuen Zustand zur späteren Routenrekonstruktion
                    arrival_states[next_station].append((planned_arrival_time, planned_departure_time, new_transfers, train))

                    # Speichere zusätzliche Verspätungsinformationen zur Verbindung
                    prediction_information[(current_stop, next_station, train)] = {
                        "zugtyp": zugtyp,
                        "halt_nummer": halt_nummer,
                        "train_avg_30": train_avg_30,
                        "station_avg_30": station_avg_30
                    }

                    # Wenn Verbindung besser ist, aktualisiere best arrival info
                    if is_better:
                        arrival_info[next_station] = (planned_arrival_time, new_transfers)

                    # Speichere vorherigen Zustand (für späteren Pfadaufbau)
                    state_key = (next_station, planned_arrival_time, train)
                    previous_stop[state_key] = current_stop
                    previous_train[state_key] = current_train

                    # Merke den ersten verwendeten Zug für spätere Filterlogik
                    if current_train is None:
                        first_train_used[state_key] = train
                    else:
                        first_train_used[state_key] = first_train_used.get((current_stop, arrival_time, current_train), train)

                    # Neuen Zustand zur Warteschlange hinzufügen
                    heapq.heappush(queue_local, (planned_arrival_time, next_station, train, new_transfers))



    # (4) Kontrollgerüst der Routenplanung - zentrale Schleife, die bestimmt, wie oft und mit welchen Parametern neue Routen versucht werden
    attempt = 0
    while attempt < max_attempts:
        if time.time() > deadline_time:
            print(f"\n⏱️ Zeitlimit von {max_duration_seconds} Sekunden erreicht, breche ab.")
            break
        # Reset für neuen Versuch
        arrival_info.clear()
        arrival_info[source] = (current_departure_time, 0)
        arrival_states[source].append((current_departure_time, current_departure_time, 0, None))


        # 1. Versuch: Normal starten ab aktueller Abfahrtszeit
        verarbeite_verbindungen(current_departure_time)
        
        # 2. Falls keine Routen gefunden, nochmal Versuch ab Mitternacht (Index 0)
        if not all_target_routes:
            print("🔁 Weniger als 4 Routen gefunden, erneuter Versuch ab Mitternacht (Index 0)")
            verarbeite_verbindungen(current_departure_time, start_idx_override=0)

        # 3. Prüfen, ob wir genügend Routen haben
        filtered_routes = filter_and_sort_routes(all_target_routes)

        if len(filtered_routes) >= 4:
            break
        else:
            print(f"❗ Nur {len(filtered_routes)} gefilterte Routen, versuche es erneut.")


        # 4. Wenn nicht genug, Abfahrtszeit um delay_hours erhöhen für nächsten Versuch
        current_departure_time += timedelta(hours=delay_hours)
        attempt += 1

    if not all_target_routes:
        print("\n❌ Keine Verbindung gefunden!")
        return None

    
    sorted_routes = filter_and_sort_routes(all_target_routes)
    best_routes = sorted_routes[:4]

    
    detailed_routes = []
    for (target_key, _transfers) in best_routes:
        detailed = reconstruct_route_details(
            previous_stop, previous_train, arrival_states,
            source, target_key, station_departures, travel_date,
            prediction_information
        )
        if detailed:
            detailed_routes.append(detailed)

    print(f"\n✅ Gesamtdauer der Routenplanung: {time.time() - start_time_total:.2f} Sekunden")
    print(f"🔁 Durchläufe der Warteschlange: {iteration_count}")
    print(f"🔎 Geprüfte Verbindungen: {verbindung_counter}")
    return detailed_routes


# Testausgabe von Routen

if __name__ == "__main__":
    
    # Versuche Pickle-Datei zu laden
    station_departures = load_station_departures_pickle()

    # Falls keine Pickle-Datei vorhanden ist, neu erstellen und speichern
    if station_departures is None:
        station_departures = create_station_departures_from_db()
        #print("✅ station_departures erstellt!")
        save_station_departures_pickle(station_departures)

    

    # Beispielhafte Eingaben
    source = "München Hbf"
    target = "Würzburg"

    # 📅 Datum und Uhrzeit für Abfahrt
    travel_date = datetime.strptime("2025-04-15", "%Y-%m-%d").date()
    departure_time = datetime.combine(travel_date, datetime.strptime("11:00", "%H:%M").time())

    # Routenberechnung aufrufen
    detailed_routes = routenplanung(source, target, station_departures, departure_time, travel_date=travel_date)

    # Ausgabe
    if detailed_routes:
        print("\n📋 Detaillierte Routen:")
        for idx, route in enumerate(detailed_routes, start=1):
            print(f"\n🔁 Route {idx}:")
            for leg in route:
                print(
                    f"🚆 {leg['train_number']} ({leg.get('zugtyp', '?')}) "
                    f"| Halt-Nummer: {leg.get('halt_nummer', '?')} "
                    f"| Train-Avg-30: {leg.get('train_avg_30', '?')} "
                    f"| Station-Avg-30: {leg.get('station_avg_30', '?')}"
                )
                print(
                    f"    Von {leg['station_name_from']} um {leg['planned_departure_from'].strftime('%H:%M')} "
                    f"nach {leg['station_name_to']} (Ankunft {leg['planned_arrival_to'].strftime('%H:%M')}) "
                    f"am {leg['planned_arrival_date_from']}"
                )

                # 🆕 Umsteigeinfo ausgeben, falls vorhanden
                if leg.get("umsteigeort"):
                    print(
                        f"    🔄 Umstieg in {leg['umsteigeort']} "
                        f"| Umsteigezeit: {leg['umsteigezeit_minuten']:.0f} Minuten"
                    )

    else:
        print("❌ Keine Route gefunden.")






