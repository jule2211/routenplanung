import pandas as pd
import heapq
from datetime import datetime, timedelta
import pickle
import os
import bisect  
from collections import defaultdict, Counter
import time
import psycopg2
import math
from math import radians, cos, sin, sqrt, atan2



# Die folgenden Methoden sind nicht in die finale Lösung integriert.
# Beschränkt den Suchraum auf einen Bereich, der durch die Start- und Zielstationen definiert ist, 
# wie in Fan und Shi (2010) vorgeschlagen.


"""
stellt eine Verbindung zur Datenbank her, 
liest die Koordinaten (Breitengrad und Längengrad) aller Stationen aus der Stationstabelle 
und gibt sie als Wörterbuch im Format {Stationsname: (Breitengrad, Längengrad)} zurück.
"""

def get_station_coordinates():

    connection = psycopg2.connect(
            host="35.246.149.161",
            port=5432,
            dbname="postgres",
            user="postgres",
            password="UWP12345!"
        )
    query_stations = """
        SELECT station_name, latitude, longitude
        FROM stations;
    """
    stations_df = pd.read_sql(query_stations, connection)

    station_coordinates = {}
    for _, row in stations_df.iterrows():
        station = row["station_name"]
        lat = row["latitude"]
        lon = row["longitude"]
        if pd.notna(lat) and pd.notna(lon):
            station_coordinates[station] = (lat, lon)

    connection.close()

    return station_coordinates


def load_station_coordinates_pickle(filename="station_coordinates.pkl"):
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            data = pickle.load(f)
            if isinstance(data, dict) and data:
                return data
            else:
                print("Keine gültige station_coordinates Pickle-Datei gefunden.")
    return None

def save_station_coordinates_pickle(data, filename="station_coordinates.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(data, f)
    print(f"station_coordinates wurde als Pickle-Datei gespeichert: {filename}")


"""berechnet die Luftlinienentfernung
zwischen zwei Punkten auf der Erde anhand ihrer geografischen Koordinaten
"""

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c



"""
prüft, ob eine gegebene Station in der Nähe einer Strecke 
zwischen zwei geografischen Punkten (Start und Ziel) liegt 
– inklusive eines seitlichen Puffers (z. B. 20 km) und optionaler Verlängerung vor dem Start und nach dem Ziel (z. B. 20 % der Streckenlänge).
"""

def station_in_extended_rectangle(lat, lon, source_lat, source_lon, target_lat, target_lon, buffer_km=300, extend_ratio=0.2):
    # Richtungsvektor der Verbindung S → D
    dx = target_lon - source_lon
    dy = target_lat - source_lat
    length = math.sqrt(dx**2 + dy**2)
    if length == 0:
        return False

    # Normieren
    dx /= length
    dy /= length

    # Vektor vom Start zur aktuellen Station
    sx = lon - source_lon
    sy = lat - source_lat

    # Projektion der Station auf die Linie (Skalarprodukt)
    projection = sx * dx + sy * dy

    # Position auf der Linie (zurückgerechnet)
    closest_x = source_lon + projection * dx
    closest_y = source_lat + projection * dy

    # Orthogonaler Abstand zur Linie
    orth_dist_km = haversine_distance(lat, lon, closest_y, closest_x)

    # Gesamtdistanz der Strecke in km
    total_distance_km = haversine_distance(source_lat, source_lon, target_lat, target_lon)

    # Toleranzbereich entlang der Strecke erweitern
    min_proj = -extend_ratio
    max_proj = 1.0 + extend_ratio

    # Normierte Projektion relativ zur Strecke
    normalized_proj = projection / length

    # Bedingung: in erweiterter Strecke und seitlich im Puffer
    if (min_proj <= normalized_proj <= max_proj) and (orth_dist_km <= buffer_km):
        return True
    return False


def routenplanung(source, target, station_departures, departure_time, buffer_minutes=800, min_transfer_minutes=5,  
                  max_initial_wait_hours=8, max_transfer_wait_hours=2, travel_date=None,
                  max_attempts=6, delay_hours=2, station_coordinates = None):
    
    start_time_total = time.time()
    max_duration_seconds = 5  
    deadline_time = start_time_total + max_duration_seconds

    if travel_date is None:
        travel_date = datetime.today().date()

    min_transfer_time = timedelta(minutes=min_transfer_minutes)





    # ab hier Integration von station_in_extended_rectangle

    radius_buffer_km = 200  
    radius_km = 9999  
    allowed_stations = set(station_departures.keys())

    if station_coordinates and source in station_coordinates and target in station_coordinates:
        source_lat, source_lon = station_coordinates[source]
        target_lat, target_lon = station_coordinates[target]
        dist_source_target = haversine_distance(source_lat, source_lon, target_lat, target_lon)
        print(f"📐 Entfernung Quelle → Ziel: {dist_source_target:.2f} km")
        print(f"⬛ Rechteck mit seitlichem Puffer von {radius_buffer_km} km wird verwendet.")

        allowed_stations = {
            station for station, (lat, lon) in station_coordinates.items()
            if station_in_extended_rectangle(lat, lon, source_lat, source_lon, target_lat, target_lon, buffer_km=radius_buffer_km)
        }

        print(allowed_stations)

    else:
        print(f"⚠️ Koordinaten von {source} oder {target} fehlen – suche ohne Rechtecks-Filter.")

    



    
    # ab hier wie in finaler Lösung
    previous_stop = {}
    previous_train = {}
    arrival_info = defaultdict(lambda: (datetime.max, float("inf")))
    arrival_states = defaultdict(list)
    prediction_information = {}
    first_train_used = {}
    all_target_routes = set()

    verbindung_counter = 0
    iteration_count = 0

    current_departure_time = departure_time

    def filter_and_sort_routes(all_routes_set):
        best_routes_map = {}
        for (station, arrival_time, train), transfers in all_routes_set:
            first_train = first_train_used.get((station, arrival_time, train), "?")
            key = (station, arrival_time, first_train)
            if key not in best_routes_map or transfers < best_routes_map[key][1]:
                best_routes_map[key] = ((station, arrival_time, train), transfers)

        time_window_minutes = 30
        routes_by_start_train = defaultdict(list)
        for (station, arrival_time, first_train), (route_info, transfers) in best_routes_map.items():
            routes_by_start_train[first_train].append((station, arrival_time, route_info, transfers))

        filtered = []
        for first_train, routes in routes_by_start_train.items():
            routes.sort(key=lambda x: x[1])
            best_station, best_arrival_time, best_route_info, best_transfers = routes[0]
            filtered.append((best_route_info, best_transfers))
            for station, arrival_time, route_info, transfers in routes[1:]:
                delta_minutes = (arrival_time - best_arrival_time).total_seconds() / 60
                if delta_minutes <= time_window_minutes and transfers <= best_transfers:
                    filtered.append((route_info, transfers))
                elif delta_minutes > time_window_minutes and transfers < best_transfers:
                    filtered.append((route_info, transfers))

        return sorted(filtered, key=lambda x: x[0][1])

    def verarbeite_verbindungen(current_departure_time, start_idx_override=None):
        nonlocal verbindung_counter, iteration_count
        queue_local = [(current_departure_time, source, None, 0)]
        heapq.heapify(queue_local)

        while queue_local:
            arrival_time, current_stop, current_train, transfers = heapq.heappop(queue_local)
            iteration_count += 1

            if current_stop == target:
                all_target_routes.add(((current_stop, arrival_time, current_train), transfers))
                continue

            if current_stop not in allowed_stations:
                print(current_stop)
                continue


            connections = station_departures[current_stop]
            arrival_time_only = arrival_time.time() if isinstance(arrival_time, datetime) else arrival_time

            if start_idx_override is not None:
                start_idx = start_idx_override
            else:
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

                while planned_departure_time < arrival_time:
                    planned_departure_time += timedelta(days=1)
                    planned_arrival_time += timedelta(days=1)

                wartezeit = (planned_departure_time - arrival_time).total_seconds() / 3600
                max_wait = max_initial_wait_hours if current_train is None else max_transfer_wait_hours

                if wartezeit > max_wait:
                    continue

                new_transfers = transfers
                if current_train is not None and train != current_train:
                    new_transfers += 1
                    if (planned_departure_time - arrival_time) < min_transfer_time:
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

                if (is_better or within_buffer):
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

                    heapq.heappush(queue_local, (planned_arrival_time, next_station, train, new_transfers))

    attempt = 0
    while attempt < max_attempts:
        if time.time() > deadline_time:
            print(f"\n⏱️ Zeitlimit von {max_duration_seconds} Sekunden erreicht, breche ab.")
            break
        
        arrival_info.clear()
        arrival_info[source] = (current_departure_time, 0)
        arrival_states[source].append((current_departure_time, current_departure_time, 0, None))
        prediction_information.clear()
        

        verarbeite_verbindungen(current_departure_time)
        

        if not all_target_routes:
            print("🔁 Weniger als 4 Routen gefunden, erneuter Versuch ab Mitternacht (Index 0)")
            verarbeite_verbindungen(current_departure_time, start_idx_override=0)

        
        filtered_routes = filter_and_sort_routes(all_target_routes)

        if len(filtered_routes) >= 4:
            break
        else:
            print(f"❗ Nur {len(filtered_routes)} gefilterte Routen, versuche es erneut.")


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








"""
Die folgenden Methoden sind unverändert zu finalen Lösung
"""

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

    
    df["planned_departure"] = pd.to_datetime(df["planned_departure"], format="%H:%M:%S", errors="coerce").dt.time
    df["planned_arrival"] = pd.to_datetime(df["planned_arrival"], format="%H:%M:%S", errors="coerce").dt.time
    df.sort_values(by=["train_number", "reihenfolge"], inplace=True)

    df["next_station"] = df.groupby("train_number")["station_name"].shift(-1)
    df["next_arrival"] = df.groupby("train_number")["planned_arrival"].shift(-1)

    station_departures = defaultdict(list)
    base_date = datetime.today().date()

    for _, row in df.iterrows():
        train = row["train_number"]
        from_station = row["station_name"]
        to_station = row["next_station"]
        dep_time = row["planned_departure"]
        arr_time = row["next_arrival"]

        zugtyp = row["zugtyp"]
        halt_nummer = row["reihenfolge"] if pd.notna(row["reihenfolge"]) else None
        train_avg_30 = row["train_avg_30"]
        station_avg_30 = row["station_avg_30"]

        
        if pd.isna(dep_time) or pd.isna(arr_time) or pd.isna(to_station):
            continue

        dep_dt = datetime.combine(base_date, dep_time)
        arr_dt = datetime.combine(base_date, arr_time)

        station_departures[from_station].append((
            train, to_station, dep_dt, arr_dt,
            zugtyp, halt_nummer, train_avg_30, station_avg_30
        ))

    
    for connections in station_departures.values():
        connections.sort(key=lambda x: x[2])  

    return dict(station_departures)


def load_station_departures_pickle(filename="station_departure_2.pkl"):
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            data = pickle.load(f)
            if isinstance(data, dict) and data:
                return data
            else:
                print(" Keine Pickle-Datei gefunden")
    return None  

def save_station_departures_pickle(data, filename="station_departure_2.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(data, f)
    print(f" station_departures wurde als Pickle-Datei gespeichert: {filename}")


def reconstruct_route_details(previous_stop, previous_train, arrival_states, source, target_key, station_departures, travel_date, prediction_information):
   
    route = []
    station, arrival_time, train = target_key
    visited = set()
    next_dep_time = None
    pending_transfer_info = None

    step = 0

    while (station, arrival_time, train) in previous_stop:
        step += 1
       
        if (station, arrival_time, train) in visited:
            
            return None
        visited.add((station, arrival_time, train))

        prev_station = previous_stop[(station, arrival_time, train)]
        prev_train = previous_train.get((station, arrival_time, train), None)


        dep_time = None
        arrival_time_prev = None

        arrival_list = arrival_states.get(prev_station, [])
       

        for (t_arrival, t_departure, transfers, tr) in arrival_list:
            if tr == prev_train and t_arrival <= arrival_time:
                dep_time = t_departure
                arrival_time_prev = t_arrival
                break

        if dep_time is None:
            break

        if next_dep_time is not None:
            departure_used = next_dep_time
        else:
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
            pending_transfer_info = None  

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
      

        route.append(route_entry)

        
        if (train != prev_train) and (prev_train is not None):
            umsteigezeit_minuten_jetzt = (departure_used - arrival_time_prev).total_seconds() / 60
            pending_transfer_info = (prev_station, umsteigezeit_minuten_jetzt)


        
        station = prev_station
        train = prev_train
        arrival_time = arrival_time_prev
        next_dep_time = dep_time

    route.reverse()
    return route




def find_start_index(connections, arrival_time_only):
    for idx, conn in enumerate(connections):
        train, next_station, dep_time, arr_time, zugtyp, halt_nummer, train_avg_30, station_avg_30 = conn

        if isinstance(dep_time, datetime):
            dep_time_only = dep_time.time()
        else:
            dep_time_only = dep_time

   
        if dep_time_only >= arrival_time_only:
            return idx

    return 0



