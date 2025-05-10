# mit station_departures und db, die 4 schnellsten Routen, auch Ausgabe von first_train_used in all_target_routes
# wie test2
# Abfahrten über Nacht 
# inkl. station_avg_30 etc.
# inkl. Umsteigeinfos
# versuch über nacht zu verbessern


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
               ankunft_geplant AS planned_arrival, halt_nummer AS reihenfolge,
               zugtyp, train_avg_30, station_avg_30
        FROM sollfahrplan_reihenfolge
        ORDER BY zug, halt_nummer;
    """

    df = pd.read_sql(query, connection)
    connection.close()

    # Zeiten als Zeit-Objekte umwandeln
    df["planned_departure"] = pd.to_datetime(df["planned_departure"], format="%H:%M:%S", errors="coerce").dt.time
    df["planned_arrival"] = pd.to_datetime(df["planned_arrival"], format="%H:%M:%S", errors="coerce").dt.time

    # Sortieren nach Zug und Reihenfolge
    df.sort_values(by=["train_number", "reihenfolge"], inplace=True)

    # nächste Station vorberechnen
    df["next_station"] = df.groupby("train_number")["station_name"].shift(-1)
    df["next_arrival"] = df.groupby("train_number")["planned_arrival"].shift(-1)

    station_departures = defaultdict(list)

    current_train = None
    day_offset = 0
    last_dep_dt = None

    for _, row in df.iterrows():
        train = row["train_number"]
        from_station = row["station_name"]
        to_station = row["next_station"]
        dep_time = row["planned_departure"]
        arr_time = row["next_arrival"]

        zugtyp = row["zugtyp"]  # 🚩 Zugtyp für from_station
        halt_nummer = row["reihenfolge"] if pd.notna(row["reihenfolge"]) else None  # 🚩 Halt-Nummer für from_station
        train_avg_30 = row["train_avg_30"]  # 🚩 Avg-Werte für from_station
        station_avg_30 = row["station_avg_30"]

        # Skip wenn keine gültigen Abfahrts-/Ankunftsdaten
        if pd.isna(dep_time) or pd.isna(arr_time) or pd.isna(to_station):
            continue

        if train != current_train:
            current_train = train
            day_offset = 0
            last_dep_dt = None

        base_date = datetime.today().date()
        dep_dt = datetime.combine(base_date + timedelta(days=day_offset), dep_time)
        arr_dt = datetime.combine(base_date + timedelta(days=day_offset), arr_time)

        # Tagwechsel-Logik
        if last_dep_dt and dep_dt < last_dep_dt:
            day_offset += 1
            dep_dt = datetime.combine(base_date + timedelta(days=day_offset), dep_time)
            arr_dt = datetime.combine(base_date + timedelta(days=day_offset), arr_time)

        if arr_dt < dep_dt:
            arr_dt += timedelta(days=1)

        last_dep_dt = dep_dt

        station_departures[from_station].append((
            train, to_station, dep_dt, arr_dt,
            zugtyp, halt_nummer, train_avg_30, station_avg_30
        ))

    for connections in station_departures.values():
        connections.sort(key=lambda x: x[2])  # Sortieren nach Abfahrt

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

def reconstruct_route_details(previous_stop, previous_train, arrival_states, source, target_key, station_departures, travel_date, prediction_information):
    import pprint
    pp = pprint.PrettyPrinter(indent=2)

    #print("\n=== Starte reconstruct_route_details ===")
    #print(f"Target Key: {target_key}")

    route = []
    station, arrival_time, train = target_key
    visited = set()
    next_dep_time = None
    pending_transfer_info = None

    step = 0

    while (station, arrival_time, train) in previous_stop:
        step += 1
        #print(f"\n--- Schritt {step}: ---")
        #print(f"Aktueller Knoten: Station={station}, Ankunft={arrival_time}, Zug={train}")

        if (station, arrival_time, train) in visited:
            #print("Zyklische Referenz entdeckt. Abbruch.")
            return None
        visited.add((station, arrival_time, train))

        prev_station = previous_stop[(station, arrival_time, train)]
        prev_train = previous_train.get((station, arrival_time, train), None)

        #print(f"Vorheriger Bahnhof: {prev_station}, Vorheriger Zug: {prev_train}")

        dep_time = None
        arrival_time_prev = None

        arrival_list = arrival_states.get(prev_station, [])
        #print(f"Arrival States für {prev_station}: {arrival_list}")

        for (t_arrival, t_departure, transfers, tr) in arrival_list:
            if tr == prev_train and t_arrival <= arrival_time:
                dep_time = t_departure
                arrival_time_prev = t_arrival
                #print(f"Gefundene passende Abfahrt: Ankunft={t_arrival}, Abfahrt={t_departure}, Zug={tr}")
                break

        if dep_time is None:
            #print(f"Keine passende Abfahrt in {prev_station} gefunden. Abbruch.")
            break

        if next_dep_time is not None:
            departure_used = next_dep_time
        else:
            # Suche die departure_time aus arrival_states
            departure_used = None
            for (arrival, departure, transfers, tr) in arrival_states.get(station, []):
                if tr == train:
                    departure_used = departure
                    break


        pred_info = prediction_information.get((prev_station, station, train), {})
        zugtyp = pred_info.get("zugtyp")
        halt_nummer = pred_info.get("halt_nummer")
        train_avg_30 = pred_info.get("train_avg_30")
        station_avg_30 = pred_info.get("station_avg_30")

        umsteigeort = None
        umsteigezeit_minuten = None
        if pending_transfer_info:
            umsteigeort, umsteigezeit_minuten = pending_transfer_info
            pending_transfer_info = None  # Reset für nächsten Abschnitt

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
        #print("Route-Eintrag:")
        #pp.pprint(route_entry)

        route.append(route_entry)

        # Falls Umstieg zwischen Zügen, merken
        if (train != prev_train) and (prev_train is not None):
            umsteigezeit_minuten_jetzt = (departure_used - arrival_time_prev).total_seconds() / 60
            pending_transfer_info = (prev_station, umsteigezeit_minuten_jetzt)
            print(f"Umstieg erkannt: neuer Umsteigeort={prev_station}, Umsteigezeit={umsteigezeit_minuten_jetzt:.1f} min")

        # Vorbereitung für nächsten Loop-Durchlauf
        station = prev_station
        train = prev_train
        arrival_time = arrival_time_prev
        next_dep_time = dep_time

    route.reverse()

    #print("\n=== Rekonstruktion abgeschlossen ===")
    #print("Finale Route:")
    #pp.pprint(route)
    return route



"""
def find_start_index(connections, min_dep_time):
    dep_times = [datetime.combine(datetime.today(), conn[2].time()) if isinstance(conn[2], datetime) else datetime.combine(datetime.today(), conn[2]) for conn in connections]
    min_dep_dt = datetime.combine(datetime.today(), min_dep_time)
    return bisect.bisect_left(dep_times, min_dep_dt)
"""

def find_start_index(connections, arrival_time_only):
    for idx, conn in enumerate(connections):
        train, next_station, dep_time, arr_time, zugtyp, halt_nummer, train_avg_30, station_avg_30 = conn

        # Stelle sicher, dass dep_time ein datetime.time Objekt ist
        if isinstance(dep_time, datetime):
            dep_time_only = dep_time.time()
        else:
            dep_time_only = dep_time

        # Wenn Abfahrtszeit nach (>=) Ankunftszeit liegt, nehmen wir diese Verbindung
        if dep_time_only >= arrival_time_only:
            return idx

    # Wenn keine spätere Abfahrt gefunden wird ➔ ab Index 0 neu prüfen (nächster Tag)
    return 0




def routenplanung(source, target, station_departures, departure_time, buffer_minutes=8000, min_transfer_minutes=5,  
                  max_initial_wait_hours=8, max_transfer_wait_hours=2, travel_date=None):
    start_time_total = time.time()
    if travel_date is None:
        travel_date = datetime.today().date()

    min_transfer_time = timedelta(minutes=min_transfer_minutes)

    previous_stop = {}
    previous_train = {}
    arrival_info = defaultdict(lambda: (datetime.max, float("inf")))
    arrival_info[source] = (departure_time, 0)

    arrival_states = defaultdict(list)
    arrival_states[source].append((departure_time, departure_time, 0, None))

    prediction_information = {}  # <-- Neu: Umbenannt und erweitert

    first_train_used = {}
    all_target_routes = set()
    queue = []
    heapq.heappush(queue, (departure_time, source, None, 0))
    verbindung_counter = 0
    iteration_count = 0

    while queue:
        arrival_time, current_stop, current_train, transfers = heapq.heappop(queue)

        if current_stop == target:
            all_target_routes.add(((current_stop, arrival_time, current_train), transfers))
            continue

        if current_stop not in station_departures:
            continue

        connections = station_departures[current_stop]
        if isinstance(arrival_time, datetime):
            arrival_time_only = arrival_time.time()
        else:
            arrival_time_only = arrival_time

        start_idx = find_start_index(connections, arrival_time_only)

        for i in range(start_idx, len(connections)):
            verbindung_counter += 1
            (train, next_station, dep_time, arr_time, zugtyp, halt_nummer, train_avg_30, station_avg_30) = connections[i]

            dep_time = dep_time.time() if isinstance(dep_time, datetime) else dep_time
            arr_time = arr_time.time() if isinstance(arr_time, datetime) else arr_time
            planned_departure_time = datetime.combine(travel_date, dep_time)
            planned_arrival_time = datetime.combine(travel_date, arr_time)

            if planned_arrival_time <= planned_departure_time:
                planned_arrival_time += timedelta(days=1)

            if planned_departure_time.date() != arrival_time.date():
                planned_departure_time += timedelta(days=1)
                planned_arrival_time += timedelta(days=1)

            if planned_departure_time < arrival_time:
                planned_departure_time += timedelta(days=1)
                planned_arrival_time += timedelta(days=1)

            

            if planned_departure_time < arrival_time:
                """
                if current_stop == "Ingolstadt Hbf":
                    print(f"⏭️ Verworfen (Abfahrt {planned_departure_time.strftime('%H:%M')} < aktuelle Ankunft {arrival_time.strftime('%H:%M')})")
                    print(planned_departure_time.date(), arrival_time.date())
                """
                continue

            wartezeit = (planned_departure_time - arrival_time).total_seconds() / 3600
            max_wait = max_initial_wait_hours if current_train is None else max_transfer_wait_hours

            if wartezeit > max_wait:
                """
                if current_stop == "Hamburg Hbf":
                    print(f"⏭️ Verworfen (Wartezeit {wartezeit:.2f}h > max. {max_wait}h)")
                """
                continue

            valid_transfer = True
            new_transfers = transfers

            if current_train is not None and train != current_train:
                new_transfers += 1
                if (planned_departure_time - arrival_time) < min_transfer_time:
                    """
                    if current_stop == "Hamburg Hbf":
                        print(f"⏭️ Verworfen (Umsteigezeit {(planned_departure_time - arrival_time).total_seconds()/60:.1f}min zu kurz)")
                    """
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
                arrival_states[next_station].append((planned_arrival_time, planned_departure_time, new_transfers, train))

                prediction_information[(current_stop, next_station, train)] = {
                    "zugtyp": zugtyp,
                    "halt_nummer": halt_nummer,
                    "train_avg_30": train_avg_30,
                    "station_avg_30": station_avg_30
                }

                if is_better:
                    arrival_info[next_station] = (planned_arrival_time, new_transfers)

                state_key = (next_station, planned_arrival_time, train)
                previous_stop[state_key] = current_stop
                previous_train[state_key] = current_train

                if current_train is None:
                    first_train_used[state_key] = train
                else:
                    first_train_used[state_key] = first_train_used.get((current_stop, arrival_time, current_train), train)

                heapq.heappush(queue, (planned_arrival_time, next_station, train, new_transfers))
                """
                if current_stop == "Hamburg Hbf":
                    print(f"✅ Verbindung hinzugefügt: Zug {train} ab {current_stop} ({planned_departure_time.strftime('%H:%M')}) "
                          f"nach {next_station} (Ankunft {planned_arrival_time.strftime('%H:%M')}) | Umstiege: {new_transfers}")

                """

    if not all_target_routes:
        print("\n❌ Keine Verbindung gefunden!")
        return None

    print("\n🧪 [DEBUG] Alle gefundenen Zielrouten:")
    for (station, arrival_time, train), transfers in sorted(all_target_routes, key=lambda x: x[0][1]):
        first_train = first_train_used.get((station, arrival_time, train), "?")
        print(f"  🎯 {station} erreicht um {arrival_time.strftime('%H:%M')} mit Zug {train}, gestartet mit Zug {first_train}, Umstiege: {transfers}")

    # Gruppieren und beste Verbindung (mit wenigsten Umstiegen) behalten
    # Gruppieren und beste Verbindung (mit wenigsten Umstiegen) behalten
    best_routes_map = {}

    for (station, arrival_time, train), transfers in all_target_routes:
        first_train = first_train_used.get((station, arrival_time, train), "?")
        key = (station, arrival_time, first_train)
        if key not in best_routes_map or transfers < best_routes_map[key][1]:
            best_routes_map[key] = ((station, arrival_time, train), transfers)

        # 🔥 Zusätzlicher Block danach:
    time_window_minutes = 30  # Maximales Zeitfenster für spätere Ankünfte (in Minuten)

    # Sortiere alle Routen nach Startzug
    routes_by_start_train = defaultdict(list)
    for (station, arrival_time, train_first_train), (route_info, transfers) in best_routes_map.items():
        routes_by_start_train[train_first_train].append((station, arrival_time, route_info, transfers))

    filtered_routes = []

    for first_train, routes in routes_by_start_train.items():
        # Sortiere pro Startzug die Verbindungen nach Ankunftszeit
        routes.sort(key=lambda x: x[1])

        best_station, best_arrival_time, best_route_info, best_transfers = routes[0]
        filtered_routes.append((best_route_info, best_transfers))  # Immer beste Verbindung behalten

        for station, arrival_time, route_info, transfers in routes[1:]:
            delta_minutes = (arrival_time - best_arrival_time).total_seconds() / 60

            if delta_minutes <= time_window_minutes:
                if transfers <= best_transfers:
                    filtered_routes.append((route_info, transfers))
                else:
                    # Innerhalb Zeitfenster aber mehr Umstiege -> nicht behalten
                    pass
            else:
                # Außerhalb Zeitfenster: nur behalten, wenn weniger Umstiege als beste Verbindung
                if transfers < best_transfers:
                    filtered_routes.append((route_info, transfers))


    # ⚡ Ersetze jetzt all_target_routes durch die neue gefilterte Menge
    all_target_routes = set(filtered_routes)


    sorted_routes = sorted(all_target_routes, key=lambda x: x[0][1])
    best_routes = sorted_routes[:6]

    detailed_routes = []
    for (target_key, _transfers) in best_routes:
        detailed = reconstruct_route_details(previous_stop, previous_train, arrival_states, source, target_key, station_departures, travel_date, prediction_information)
        if detailed:
            detailed_routes.append(detailed)

    print(f"\n✅ Gesamtdauer der Routenplanung: {time.time() - start_time_total:.2f} Sekunden")
    print(f"🔁 Durchläufe der Warteschlange: {iteration_count}")
    print(f"🔎 Geprüfte Verbindungen: {verbindung_counter}")
    return detailed_routes




if __name__ == "__main__":
    from datetime import datetime

    # Versuche Pickle-Datei zu laden
    station_departures = load_station_departures_pickle()

    # Falls keine Pickle-Datei vorhanden ist, neu erstellen und speichern
    if station_departures is None:
        station_departures = create_station_departures_from_db()
        print("✅ station_departures erstellt!")
        save_station_departures_pickle(station_departures)

    # Debug: Alle Verbindungen von Hannover Hbf ausgeben
    
    """
    if "München Hbf" in station_departures:
        print("\n🚏 Verbindungen ab München Hbf:")
        for conn in station_departures["Berlin Hbf"]:
            train, next_station, dep_dt, arr_dt, zugtyp, halt_nummer, train_avg_30, station_avg_30 = conn
            print(f"  🚆 Zug {train} ({zugtyp}) von {dep_dt.strftime('%H:%M')} nach {next_station} (Ankunft {arr_dt.strftime('%H:%M')})")
    else:
        print("❌ Keine Verbindungen ab Hannover Hbf gefunden!")
    """

    # Beispielhafte Eingaben
    source = "Baden-Baden"
    target = "Karlsruhe Hbf"

    # 📅 Datum und Uhrzeit für Abfahrt
    travel_date = datetime.strptime("2025-04-15", "%Y-%m-%d").date()
    departure_time = datetime.combine(travel_date, datetime.strptime("11:50", "%H:%M").time())

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





