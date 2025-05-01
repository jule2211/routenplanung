# mit station_departures und db, die 4 schnellsten Routen, auch Ausgabe von first_train_used in all_target_routes
# also wie test2
# zusätzlich wird allerdings versucht Abfahrten über Nacht auch möglich zu machen


import pandas as pd
import heapq
from datetime import datetime, timedelta
import pickle
import os
import bisect  
from collections import defaultdict, Counter
import time
import psycopg2


def create_station_departures_from_db():
    connection = psycopg2.connect(
        host="35.246.149.161",
        port=5432,
        dbname="postgres",
        user="postgres",
        password="UWP12345!"
    )

    query = """
        SELECT zug AS train_number, halt AS station_name, abfahrt_geplant AS planned_departure,
               ankunft_geplant AS planned_arrival, halt_nummer AS reihenfolge
        FROM sollfahrplan_reihenfolge
        ORDER BY zug, halt_nummer;
    """

    df = pd.read_sql(query, connection)
    connection.close()

    df["planned_departure"] = pd.to_datetime(df["planned_departure"], format="%H:%M:%S", errors="coerce").dt.time
    df["planned_arrival"] = pd.to_datetime(df["planned_arrival"], format="%H:%M:%S", errors="coerce").dt.time

    df.sort_values(by=["train_number", "reihenfolge"], inplace=True)
    df["next_station"] = df.groupby("train_number")["station_name"].shift(-1)
    df["next_arrival"] = df.groupby("train_number")["planned_arrival"].shift(-1)

    station_departures = defaultdict(list)

    # NEU: Tracking für Tageswechsel pro Zug
    current_train = None
    day_offset = 0
    last_dep_dt = None

    for _, row in df.iterrows():
        train = row["train_number"]
        from_station = row["station_name"]
        to_station = row["next_station"]
        dep_time = row["planned_departure"]
        arr_time = row["next_arrival"]

        if pd.isna(dep_time) or pd.isna(arr_time) or pd.isna(to_station):
            continue

        # Wenn neuer Zug beginnt, zurücksetzen
        if train != current_train:
            current_train = train
            day_offset = 0
            last_dep_dt = None

        # Zeitpunkte erzeugen
        base_date = datetime.today().date()
        dep_dt = datetime.combine(base_date + timedelta(days=day_offset), dep_time)
        arr_dt = datetime.combine(base_date + timedelta(days=day_offset), arr_time)

        # Mitternachtsübergang bei Abfahrtszeit
        if last_dep_dt and dep_dt < last_dep_dt:
            day_offset += 1
            dep_dt = datetime.combine(base_date + timedelta(days=day_offset), dep_time)
            arr_dt = datetime.combine(base_date + timedelta(days=day_offset), arr_time)

        # Ankunftszeit < Abfahrt? → korrigieren
        if arr_dt < dep_dt:
            arr_dt += timedelta(days=1)

        last_dep_dt = dep_dt

        station_departures[from_station].append((train, to_station, dep_dt, arr_dt))  # speichere als datetime!

    # sortiere nach tatsächlicher Abfahrtszeit
    for connections in station_departures.values():
        connections.sort(key=lambda x: x[2])  # x[2] ist dep_dt (datetime)

    return dict(station_departures)



def load_station_departures_pickle(filename="station_departure.pkl"):
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            data = pickle.load(f)
            if isinstance(data, dict) and data:
                return data
            else:
                print(" Keine Pickle-Datei gefunden")
    return None  

def save_station_departures_pickle(data, filename="station_departure.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(data, f)
    print(f" station_departures wurde als Pickle-Datei gespeichert: {filename}")

def reconstruct_route_details(previous_stop, previous_train, arrival_states, source, target_key, station_departures, travel_date):
    route = []
    station, arrival_time, train = target_key
    visited = set()
    next_dep_time = None
    while (station, arrival_time, train) in previous_stop:
        if (station, arrival_time, train) in visited:
            return None
        visited.add((station, arrival_time, train))
        prev_station = previous_stop[(station, arrival_time, train)]
        prev_train = previous_train.get((station, arrival_time, train), None)
        dep_time = None
        arrival_time_prev = None
        for t_arrival, t_departure, transfers, tr in arrival_states.get(prev_station, []):
            if tr == prev_train and t_arrival <= arrival_time:
                dep_time = t_departure
                arrival_time_prev = t_arrival
                break
        if dep_time is None:
            break
        departure_used = next_dep_time if next_dep_time is not None else dep_time
        route.append({
            "station_name_from": prev_station,
            "station_name_to": station,
            "planned_departure_from": departure_used,
            "planned_arrival_to": arrival_time,
            "train_number": train,
            "planned_arrival_date_from": departure_used.date()
        })
        station = prev_station
        train = prev_train
        arrival_time = arrival_time_prev
        next_dep_time = dep_time
    route.reverse()
    return route

def find_start_index(connections, min_dep_time):
    dep_times = [datetime.combine(datetime.today(), conn[2].time()) if isinstance(conn[2], datetime) else datetime.combine(datetime.today(), conn[2]) for conn in connections]
    min_dep_dt = datetime.combine(datetime.today(), min_dep_time)
    return bisect.bisect_left(dep_times, min_dep_dt)

def routenplanung(source, target, station_departures, departure_time, buffer_minutes=300, min_transfer_minutes=5,  
                  max_initial_wait_hours=4, max_transfer_wait_hours=2, travel_date=None):
    start_time_total = time.time()
    if travel_date is None:
        travel_date = datetime.today().date()

    min_transfer_time = timedelta(minutes=min_transfer_minutes)

    previous_stop = {}
    previous_train = {}
    arrival_info = defaultdict(lambda: (datetime.max, float("inf")))
    arrival_info[source] = (departure_time, 0)

    # Struktur: (ankunftszeit, abfahrtszeit, transfers, zug)
    arrival_states = defaultdict(list)
    arrival_states[source].append((departure_time, departure_time, 0, None))

    # NEU: Erster verwendeter Zug pro Zustand
    first_train_used = {}

    all_target_routes = set()
    queue = []
    heapq.heappush(queue, (departure_time, source, None, 0))
    verbindung_counter = 0
    iteration_count = 0

    while queue:
        
        arrival_time, current_stop, current_train, transfers = heapq.heappop(queue)

        #print(f"🔄 Verarbeite: {current_stop} um {arrival_time.strftime('%H:%M')} mit Zug {current_train}")

        iteration_count += 1

        if current_stop == target:
            all_target_routes.add(((current_stop, arrival_time, current_train), transfers))
            continue

        if current_stop not in station_departures:
            continue

        connections = station_departures[current_stop]
        arrival_time_only = arrival_time.time()
        start_idx = find_start_index(connections, arrival_time_only)

        for i in range(start_idx, len(connections)):
            verbindung_counter += 1
            train, next_station, dep_time, arr_time = connections[i]

            dep_time = dep_time.time() if isinstance(dep_time, datetime) else dep_time
            arr_time = arr_time.time() if isinstance(arr_time, datetime) else arr_time
            planned_departure_time = datetime.combine(travel_date, dep_time)
            planned_arrival_time = datetime.combine(travel_date, arr_time)


            # 🔄 Falls Verbindung über Mitternacht geht → Ankunft ist am nächsten Tag
            if planned_arrival_time <= planned_departure_time:
                planned_arrival_time += timedelta(days=1)

            # 🕓 Falls geplante Abfahrt nicht am selben Tag wie aktuelle Ankunft → Datum korrigieren
            if planned_departure_time.date() != arrival_time.date():
                #print("Abfahrt ungleich Ankunft")
                planned_departure_time += timedelta(days=1)
                planned_arrival_time += timedelta(days=1)


            #print(f"🔍 Prüfe Verbindung: {current_stop} → {next_station} mit Zug {train} | Abfahrt: {planned_departure_time}, Ankunft: {planned_arrival_time} | Ankunftszeit aktuell: {arrival_time}")

            # ⛔ Verbindung startet vor aktueller Ankunftszeit → überspringen
            if planned_departure_time < arrival_time:
                #print("⛔️ Verbindung startet vor aktueller Ankunftszeit → übersprungen")
                continue

             # ➡️ Berechne Wartezeit
            wartezeit = (planned_departure_time - arrival_time).total_seconds() / 3600

            # 🎯 Unterschiedliche Max-Wartezeiten je nachdem, ob erster Zug oder Umstieg
            max_wait = max_initial_wait_hours if current_train is None else max_transfer_wait_hours

            if wartezeit > max_wait:
                continue

            if planned_departure_time < arrival_time:
                continue  # redundant, aber als Schutz doppelt sinnvoll


            valid_transfer = True
            new_transfers = transfers

            if current_train is not None and train != current_train:
                new_transfers += 1
                if (planned_departure_time - arrival_time) < min_transfer_time:
                    #print(f"⛔️ Umstieg zu kurz → übersprungen")
                    continue
            
            #print(f"✅ Verbindung wird verwendet und zur Warteschlange hinzugefügt.")

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
                arrival_states[next_station].append((planned_arrival_time, planned_departure_time, new_transfers, train))
                if is_better:
                    arrival_info[next_station] = (planned_arrival_time, new_transfers)

                state_key = (next_station, planned_arrival_time, train)
                previous_stop[state_key] = current_stop
                previous_train[state_key] = current_train

                # ⬇️ Speichere, mit welchem Zug gestartet wurde
                if current_train is None:
                    first_train_used[state_key] = train
                else:
                    first_train_used[state_key] = first_train_used.get((current_stop, arrival_time, current_train), train)

                """
                if current_stop == "Osnabrück Hbf" or current_stop == "Hamburg-Harburg":
                    print(f"➕ In Queue: {current_stop} → {next_station} mit {train} | "
                          f"Abfahrt: {planned_departure_time.strftime('%H:%M')}, "
                          f"Ankunft: {planned_arrival_time.strftime('%H:%M')}")
                """
                
                heapq.heappush(queue, (planned_arrival_time, next_station, train, new_transfers))

    if not all_target_routes:
        print("\n❌ Keine Verbindung gefunden!")
        return None

    # 🔍 DEBUG: Ausgabe aller Zielrouten mit erstem Zug
    print("\n🧪 [DEBUG] Alle gefundenen Zielrouten:")
    for (station, arrival_time, train), transfers in sorted(all_target_routes, key=lambda x: x[0][1]):
        first_train = first_train_used.get((station, arrival_time, train), "?")
        print(f"  🎯 {station} erreicht um {arrival_time.strftime('%H:%M')} mit Zug {train}, "
              f"gestartet mit Zug {first_train}, Umstiege: {transfers}")

    # Auswahl der 4 schnellsten Routen basierend auf Ankunftszeit
    sorted_routes = sorted(all_target_routes, key=lambda x: x[0][1])
    best_routes = sorted_routes[:4]

    detailed_routes = []
    for (target_key, _transfers) in best_routes:
        detailed = reconstruct_route_details(previous_stop, previous_train, arrival_states, source, target_key, station_departures, travel_date)
        if detailed:
            detailed_routes.append(detailed)

    print(f"\n✅ Gesamtdauer der Routenplanung: {time.time() - start_time_total:.2f} Sekunden")
    print(f"🔁 Durchläufe der Warteschlange: {iteration_count}")
    print(f"🔎 Geprüfte Verbindungen: {verbindung_counter}")
    return detailed_routes


if __name__ == "__main__":
    # Versuche Pickle-Datei zu laden
    station_departures = load_station_departures_pickle()

    # Falls keine Pickle-Datei vorhanden ist, neu erstellen und speichern
    if station_departures is None:
        station_departures = create_station_departures_from_db()
        print("station_departures erstellt!")
        save_station_departures_pickle(station_departures)

    
    for connection in station_departures.get("Hamburg-Harburg", []):
        train, to_station, dep_time, arr_time = connection
        print(f"Zug {train} fährt um {dep_time} in Hamburg-Harburg ab und kommt um {arr_time} in {to_station} an.")
    

    # Beispielhafte Eingaben
    source = "Berlin Hbf"
    target = "Nürnberg Hbf"

    # 📅 Datum und Uhrzeit für Abfahrt
    travel_date = datetime.strptime("2025-04-15", "%Y-%m-%d").date()
    departure_time = datetime.combine(travel_date, datetime.strptime("09:00", "%H:%M").time())

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

         
