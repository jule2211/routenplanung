# Replanning - method overview

## Methods

### `Replan()`
Checks whether a planned transfer is at risk due to a delay. If so, an alternative route is automatically searched for from the transfer point. The result is either a new route recommendation or None if no action is required.

**Inputs:**
- `abschnitt`: The current route section with transfer
- `route`: The entire travel route
- `station_departures`: Current departure data for all stations

**Proccess:**
1. Checks whether the transfer time is sufficient to compensate for the expected delay. 
2.  If not, a new departure time from the transfer point is calculated based on the planned arrival time + expected delay
3. Search for a new route from the transfer station using  `routenplanung()`
4. Compare the new arrival time at the destination with the old one to calculate the additional delay
5.	Result: Returns the combined new route (before the transfer + new route) and the expected delay, or `None` if no action is required

---

### `berechne_gesamtverspaetungswahrscheinlichkeit()`
This method estimates the probability (in percent) that an entire travel route will be completed successfully without major delays or missed connections.

**Eingabe:**
- `route`: List of route sections

**Procedure:**
1. Starting value: The initial probability is 100%.
2. Analyze connections: For each section with a connection, the probability of the connection working is calculated based on predefined delay categories (category_probabilities).
3. Estimation based on transfer time:
   - ≤ 10 min: Connection is considered secure with a delay of 0–9 minutes.
   - ≤ 20 min: Delays of 10–19 minutes are also considered acceptable.
   - ≤ 30 min or more: Delays of 20–29 minutes are also considered to be achievable connections.
   - Note: This categorization is an approximation. For example, if 11 minutes of transfer time are available, an actual delay of 18 minutes (from the 10–19 min category) can already lead to a missed connection – but is still considered acceptable here. However, an exact calculation is difficult with the available data.
4. The calculated probability of changing trains is multiplied by the previous total probability.
5. No transfer time is taken into account for the last section of the route. Instead, the only thing that counts is whether the train arrives at the destination station on time or with a maximum delay of 9 minutes. This probability is also multiplied by the total probability.
6. Return is the total probability in percent that the entire route will function without critical delays or missed connections.

---

### `analyse_and_replan()`
This method checks a list of detailed routes for possible transfer problems due to delays, plans alternatives if necessary, and provides estimates of delays and punctuality.

**Inputs:**
- `detailed_routes`: List of all routes to be analyzed
- `station_departures`: Departure data for all stations

**Procedure:**
1. Initialize a dictionary (`new_route_info`) for each route with:
   - original_route: the original route
   - alternative_route_info: alternative routes in case of problems
   - expected_total_delay_minutes: estimated delay for the entire route
   - total_delay_probability: probability of punctuality for the entire route
2. Use `Replan()` to check each section for transfer problems
3. If a delay is detected, save an alternative route 
4. The first delay detected due to a missed transfer is taken as the expected total delay – assuming that an alternative route will be used from this point onwards and that the other sections will be adjusted accordingly. If there are no critical transfers, the predicted delay for the last section is used.
5. Calculates the total probability with `calculate_total_delay_probability()`
6. Provides the analysis results, including possible alternatives, delay estimates, and punctuality probabilities.

---

## responsibility

Jule

---

