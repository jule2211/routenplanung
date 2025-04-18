import pandas as pd
import heapq
from datetime import datetime, timedelta
import pickle
import os
import bisect  
from collections import defaultdict, Counter
import time


def create_station_departures(file_path):

    """
    Erstellt ein Dictionary aller Zugverbindungen,
    Gruppiert nach Abfahrtsbahnhof und sortiert nach Abfahrtszeit.
    """

    # CSV einlesen und Spaltennamen vereinheitlichen
    df = pd.read_csv(file_path, delimiter=";")
    df.columns = df.columns.str.strip().str.lower()

    # Zeitspalten korrekt parsen (Format: hh:mm:ss)
    df["planned_departure"] = pd.to_datetime(
        df["planned_departure"], format="%H:%M:%S", errors="coerce"
    ).dt.time
    df["planned_arrival"] = pd.to_datetime(
        df["planned_arrival"], format="%H:%M:%S", errors="coerce"
    ).dt.time

    # Nach Zug und Reihenfolge sortieren, dann nächste Station berechnen
    df.sort_values(by=["train_number", "reihenfolge"], inplace=True)
    df["next_station"] = df.groupby("train_number")["station_name"].shift(-1)
    df["next_arrival"] = df.groupby("train_number")["planned_arrival"].shift(-1)

    # defaultdict initialisieren
    station_departures = defaultdict(list)

    # Zeilen durchgehen
    for _, row in df.iterrows():
        from_station = row["station_name"]
        to_station = row["next_station"]
        dep_time = row["planned_departure"]
        arr_time = row["next_arrival"]
        train = row["train_number"]

        if pd.isna(dep_time) or pd.isna(arr_time) or pd.isna(to_station):
            continue

        # Gültige Verbindung prüfen
        dep_dt = datetime.combine(datetime.today(), dep_time)
        arr_dt = datetime.combine(datetime.today(), arr_time)
        if dep_dt >= arr_dt:
            continue

        # Verbindung speichern (Abfahrtszeit & Ankunftszeit als datetime.time)
        station_departures[from_station].append(
            (train, to_station, dep_time, arr_time)  
        )

    # Sortiere alle Verbindungen pro Bahnhof nach Abfahrtszeit
    for connections in station_departures.values():
        connections.sort(key=lambda x: x[2])  # Sortiere nach dep_time (Index 2)

    return dict(station_departures)  #zurück in normales dict




def load_station_departures_pickle(filename="station_departures.pkl"):
    import os
    import pickle

    if os.path.exists(filename):
        with open(filename, "rb") as f:
            data = pickle.load(f)
            if isinstance(data, dict) and data:  # dict ist nicht leer
                return data
            else:
                print(" Keine Pickle-Datei gefunden")
   

    return None  



def save_station_departures_pickle(data, filename="station_departures.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(data, f)
    print(f" station_departures wurde als Pickle-Datei gespeichert: {filename}")




def reconstruct_route_details(previous_stop, previous_train, arrival_states, source, target_key, station_departures, travel_date):
    """
    Rekonstruiert die Route und gibt eine detaillierte Liste mit Abfahrt, Ankunft, Zugnummer und Datum pro Abschnitt zurück.
    """
    route = []
    station, arrival_time, train = target_key
    visited = set()
    last_train = None

    while (station, arrival_time, train) in previous_stop:
        if (station, arrival_time, train) in visited:
            return None
        visited.add((station, arrival_time, train))

        prev_station = previous_stop[(station, arrival_time, train)]
        prev_train = previous_train.get((station, arrival_time, train), None)

        dep_time = None
        for t, transfers, tr in arrival_states.get(prev_station, []):
            if tr == prev_train:
                dep_time = t
                break

        route.append({
            "station_name_from": prev_station,
            "station_name_to": station,
            "planned_departure_from": dep_time,
            "planned_arrival_to": arrival_time,
            "train_number": train,
            "planned_arrival_date_from": dep_time.date() if dep_time else travel_date
        })


        station = prev_station
        train = prev_train
        arrival_time = dep_time

        if station == source:
            break

    route.reverse()
    return route





    

def find_start_index(connections, min_dep_time):
    """
    Gibt den Index der ersten Verbindung zurück, deren Abfahrtszeit 
    (dep_time) **nicht vor** der angegebenen Mindestzeit (min_dep_time) liegt.

    Annahme: Die Verbindungen in `connections` sind nach Abfahrtszeit sortiert.
    Dadurch kann mit `bisect_left` schnell (logarithmisch) die passende Stelle gefunden werden.
    """

    dep_times = [datetime.combine(datetime.today(), conn[2]) for conn in connections]
    min_dep_dt = datetime.combine(datetime.today(), min_dep_time)
    return bisect.bisect_left(dep_times, min_dep_dt)


def routenplanung(source, target, station_departures, departure_time, buffer_minutes=300, min_transfer_minutes=5,  
           max_initial_wait_hours=2, max_transfer_wait_hours=2, travel_date=None):
    """
    Führt eine Routenplanung vom Start- zum Zielbahnhof durch, 
    wobei möglichst früh und mit minimalen Umstiegen ans Ziel gelangt wird.
    """
    import time
    start_time_total = time.time()  # Zeitmessung Start

    if travel_date is None:
        travel_date = datetime.today().date()

    # Mindest-Umstiegszeit als timedelta
    min_transfer_time = timedelta(minutes=min_transfer_minutes)

    previous_stop = {}
    previous_train = {}

    arrival_info = defaultdict(lambda: (datetime.max, float("inf")))
    arrival_info[source] = (departure_time, 0)

    arrival_states = defaultdict(list)
    arrival_states[source].append((departure_time, 0, None))

    all_target_routes = set()
    queue = []
    heapq.heappush(queue, (departure_time, source, None, 0))

    verbindung_counter = 0
    iteration_count = 0
    station_counter = Counter()

    while queue:
        arrival_time, current_stop, current_train, transfers = heapq.heappop(queue)
        iteration_count += 1

        if current_stop == target:
            all_target_routes.add(((current_stop, arrival_time, current_train), transfers))
            continue

        if current_stop in station_departures:
            connections = station_departures[current_stop]
            station_counter[current_stop] += 1  

            arrival_time_only = arrival_time.time()
            start_idx = find_start_index(connections, arrival_time_only)

            for i in range(start_idx, len(connections)):
                verbindung_counter += 1
                train, next_station, dep_time, arr_time = connections[i]

                planned_departure_time = datetime.combine(travel_date, dep_time)
                planned_arrival_time = datetime.combine(travel_date, arr_time)

                wartezeit = (planned_departure_time - arrival_time).total_seconds() / 3600
                max_wait = max_initial_wait_hours if current_train is None else max_transfer_wait_hours

                if wartezeit > max_wait:
                    break

                if planned_departure_time < arrival_time:
                    continue

                valid_transfer = True
                new_transfers = transfers

                if current_train is not None and train != current_train:
                    new_transfers += 1
                    if (planned_departure_time - arrival_time) < min_transfer_time:
                        valid_transfer = False
                        continue

                best_time, best_transfers = arrival_info[next_station]

                is_better = (
                    planned_arrival_time < best_time or
                    (planned_arrival_time == best_time and new_transfers < best_transfers)
                )

                within_buffer = (
                    best_time != datetime.max and
                    planned_arrival_time < (best_time + timedelta(minutes=buffer_minutes)) and
                    new_transfers <= best_transfers 
                )

                if (is_better or within_buffer) and valid_transfer:
                    arrival_states[next_station].append((planned_arrival_time, new_transfers, train))

                    if is_better:
                        arrival_info[next_station] = (planned_arrival_time, new_transfers)

                    state_key = (next_station, planned_arrival_time, train)
                    previous_stop[state_key] = current_stop
                    previous_train[state_key] = current_train

                    heapq.heappush(queue, (planned_arrival_time, next_station, train, new_transfers))

    if not all_target_routes:
        print("\n Keine Verbindung gefunden!")
        return None

    best_arrival_time = min(all_target_routes, key=lambda x: (x[0][1], x[1]))[0][1]
    min_transfers = min([t for (k, t) in all_target_routes if k[1] == best_arrival_time])

    best_routes = [(k, t) for (k, t) in all_target_routes if k[1] == best_arrival_time and t == min_transfers]

    for (k, t) in list(all_target_routes):
        if t == 0 and timedelta(minutes=0) < (k[1] - best_arrival_time) <= timedelta(hours=1):
            best_routes.append((k, t))

    for (k, t) in list(all_target_routes):
        if timedelta(0) < (k[1] - best_arrival_time) <= timedelta(minutes=60) and t <= min_transfers - 1:
            best_routes.append((k, t))

    best_routes = list(set(best_routes))

    detailed_routes = []
    for (target_key, _transfers) in best_routes:
        detailed = reconstruct_route_details(previous_stop, previous_train, arrival_states, source, target_key, station_departures, travel_date)
        if detailed:
            detailed_routes.append(detailed)




    print(f"\nGesamtdauer der Routenplanung: {time.time() - start_time_total:.2f} Sekunden")
    print(f"Durchläufe der Warteschlange: {iteration_count}")
    print(f"Geprüfte Verbindungen: {verbindung_counter}")

    return detailed_routes


    

if __name__ == "__main__":
    # Versuche Pickle-Datei zu laden
    station_departures = load_station_departures_pickle()

    # Falls keine Pickle-Datei vorhanden ist, aus CSV neu erstellen und speichern
    if station_departures is None:
        station_departures = create_station_departures("tabelle_verbindungen.csv")
        save_station_departures_pickle(station_departures)

    # Beispielhafte Eingaben
    source = "München Hbf"
    target = "Erfurt Hbf"

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
                    f"🚆 {leg['train_number']} von {leg['station_name_from']} nach {leg['station_name_to']} | "
                    f"{leg['planned_departure_from'].strftime('%H:%M')} → {leg['planned_arrival_to'].strftime('%H:%M')} "
                    f"am {leg['planned_arrival_date_from']}"
                )
    else:
        print("❌ Keine Route gefunden.")

         
