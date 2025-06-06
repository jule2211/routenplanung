# Route planning – methods overview

## Overview of main methods

### `create_station_departures_from_db()`
**Purpose:**  
Creates a dictionary (`station_departures`) that contains all known departures (based on the database) for each station.

**Advantages:**  
- Faster access to connections without repeated DB accesses  
- Higher performance  
- Reduced dependence on database availability  
- Integration of delay statistics to enable forecasts later (e.g., `train_avg_30`, `station_avg_30`)

**Note:**  
Since timetable data rarely changes, preprocessing is more efficient than live access.

---



### `apply_delays_to_station_departures(station_departures, delays)`
**Purpose:**
Creates a new `station_departures` dictionary adjusted to delay forecasts.

**Procedure:**  
- Takes two inputs: station_departures (planned connections per station), delays (delay forecast per connection)
- Departure and arrival times are corrected by the forecast delays.
- The adjusted connections are written to a new dictionary.
- Return: New connection structure, sorted by updated departure time

**Note:**  
This method was not used in the final solution, but was intended for robust planning.

---

### `verarbeite_verbindungen()`
**Purpose:**  
Core routing algorithm for determining optimal train connections using a priority queue (heap).

**Process:**
- **Initialization:** Start state (station, departure, no train, 0 transfers) is placed in the queue
- **Loop:** The state with the earliest arrival time is processed iteratively
- **Connection check:**
- Load connection data (train, times, destination station).
- Check and adjust arrival/departure times when the day changes.
- Check waiting times (minimum/maximum transfer time)
- Evaluation: Connection is accepted if:
    - is_better: Earlier arrival time or same early arrival time and fewer transfers.
    - within_buffer: Slightly later arrival (within buffer) and no more transfers.
- **Buffer logic:**  
    - within_buffer allows you to find connections of equal or better quality that arrive at the same time or slightly later.
    - In addition, with within_buffer more routes can be found in one run (even at later times than the specified departure_time).

- **Destination:** Stored upon arrival at the destination station, but not tracked further.

#### Comparison with Dijkstra's Algorithm

| **Similarities to Dijkstra**                                                   | **Differences from Dijkstra**                                                                                                                                             |
|--------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Priority queue – uses a min-heap queue                                         | Dijkstra uses constant edge weights. This algorithm handles time-dependent connections                                                                                   |
| Greedy principle – always processes the currently "best" known state          | Multiple criteria – not only arrival time but also transfers and buffer times are considered                                                                            |
|                                                                                | Tolerance buffer – connections that are not strictly better (e.g., within a defined tolerance range) are also added to the queue, unlike in standard Dijkstra logic     |
|                                                                                | A state is defined as `(station, arrival_time, current_train, transfers)`, while Dijkstra's state only includes the node and cost                                       |


---

### `reconstruct_route_details()`
**Purpose:**  
Reconstructs complete routes from destination to start by tracing statuses.

**Procedure:**  
- Goes backwards through previous_stop and previous_train
- Uses arrival_states to determine arrival and departure times.
- Adds additional information from prediction_information.
- Recognizes transfers and saves train changes.
- Returns the route in the correct order.

---

### `filter_and_sort_routes(all_routes_set)`
**Purpose:**  
Filters the best routes (based on transfers and arrival times) and returns them in sorted order.

**Filter criteria:**  
- If the departure train and arrival time are identical, the route with fewer transfers is retained  
- Grouping by first train (`first_train`)  
- Per group:
  - Fastest connection (earliest arrival) is always used
- Additional routes only if:
- max. 45 minutes later arrival and no more  transfers
- significantly later arrival but fewer transfers

**Return:**  
List of route tuples: `(destination station, arrival time, last train, number of transfers)`

**Purpose:**
If two routes with the same starting train exist, the variant with the later arrival only makes sense if the predicted delay of the earlier route could be so high that the later route would get you to your destination faster.
However, with an arrival time difference of more than 45 minutes, this is rather unlikely, so in this case only the more efficient route is retained.

---

### `routenplanung()`
**Purpose:**  
Calculates up to **four optimal train connections** from a starting station to a destination station.

**Parameters:**
- `source`, `target` – Start/destination
- `station_departures` – Dictionary with departures for each station
- `departure_time` – Start time (time) of the journey
- `travel_date` - optional date (default: today)
- `min_transfer_minutes` - minimum transfer time
- `max_initial_wait_hours`, `max_transfer_wait_hours` - maximum permitted waiting times at departure and transfer points
- `buffer_minutes` - how many minutes later than the current earliest arrival time at a station an arrival may be in order to still be added to the queue
- `delay_hours` - time offset for retries
- `delays` - optional delay dictionary for route calculation with delays

**Process:**
- Performs up to `max_attempts` search runs
- In each run:
  - Preparation of data structures (`arrival_info` & `arrival_states`)
  - Call `verarbeite_verbindungen()` with current start time
  - If no route is found, this is often due to a late start time (e.g., 11:00 p.m.), for which there are no connections on the same day. In this case, a second attempt is made with start_index = 0 – i.e., with the earliest possible connection on the next day
- Filtering via `filter_and_sort_routes()`
  - If <4 routes were found, try again with a delayed start time (delay_hours).
- Abort if:
  - 4 routes found
  - Time limit reached
  - Max. attempts reached
- Return: Detailed routes via `reconstruct_route_details()`

---

## auxiliary methods

| method                     | description                                             |
|-----------------------------|-----------------------------------------------------------|
| `find_start_index()`        | Finds start index for checkable connections |
| `load_station_departures_pickle()` | Loads station_departures from a pickle file     |
| `save_station_departures_pickle()` | Saves station_departures to a pickle file   |

---


## Additional methods (not integrated into the final solution)
The folder experimental/ contains additional methods that were used to try to limit the search radius and thus optimize the performance of the algorithm. `Get_station_coordinates()` establishes a connection to the database, reads the coordinates (latitude and longitude) of all stations from the stations table, and returns them as a dictionary in the format {station name: (latitude, longitude)}. Two different options were then tested:

- `haversine_distance()`: Restriction of the search area to a circular area around the starting point, with the radius defined by the distance between the starting point and destination + buffer: The code calculates the straight-line distance between two stations, extends this by a safety margin, and then filters all stations within this radius (from the starting point) within routeplanning(). Only these are added to the queue. [➡️ routen_berechnung_radius.py ansehen](../experimental/routen_berechnung_radius.py)

- `station_in_rectangle()`: Restricts the search space to an area defined by the start and destination stations, as suggested in Fan and Shi (2010): The code defines a function station_in_rectangle, which checks whether a given point (a “station”) lies within an area around the start and destination — with a lateral buffer in kilometers — and then filters all stations within this area within routeplanning(). Only these are added to the queue.   [➡️ routen_berechnung_rechteck.py ansehen](../experimental/routen_berechnung_rechteck.py)

Since this search space restriction did not significantly improve performance, but there is a risk that connections may not be found due to the restricted search space, these methods were not integrated into the final solution.

## Reference

**Title:** *Improvement of Dijkstra's Algorithm and Its Application in Route Planning*  
**Authors:** DongKai Fan, Ping Shi  
**Published in:** *IEEE Journal of Oceanic Engineering*, August 2010, Volume 13(2), Pages 1901–1904  
**DOI:** [10.1109/FSKD.2010.5569452](https://doi.org/10.1109/FSKD.2010.5569452)  
**Source:** DBLP  
**Conference:** *Seventh International Conference on Fuzzy Systems and Knowledge Discovery (FSKD 2010)*  
**Date & Location:** 10–12 August 2010, Yantai, Shandong, China





## responsibility

Jule
