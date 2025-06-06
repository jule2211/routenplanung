# Routenplanung – Methodenübersicht

## Übersicht der Hauptfunktionen

### `create_station_departures_from_db()`
**Zweck:**  
Erstellt ein Dictionary (`station_departures`), das für jeden Bahnhof alle bekannten Abfahrten (basierend auf der Datenbank) enthält.

**Vorteile:**  
- Schnellerer Zugriff auf Verbindungen ohne wiederholte DB-Zugriffe  
- Höhere Performance  
- Reduzierte Abhängigkeit von Datenbankverfügbarkeit  
- Integration von Verspätungsstatistiken um später Prognosen zu ermöglichen (z. B. `train_avg_30`, `station_avg_30`)

**Hinweis:**  
Da sich Fahrplandaten selten ändern, ist eine Vorverarbeitung effizienter als ein Live-Zugriff.

---

### `apply_delays_to_station_departures(station_departures, delays)`
**Zweck:**  
Erzeugt ein neues, an Verspätungsprognosen angepasstes `station_departures`-Dictionary.

**Vorgehen:**  
- Nimmt zwei Inputs: station_departures (geplante Verbindungen je Bahnhof), delays (Vorhersage der Verspätungen je Verbindung)
- Abfahrts- und Ankunftszeiten werden um die prognostizierten Verspätungen korrigiert.
- Die angepassten Verbindungen werden in ein neues Dictionary geschrieben.
- Rückgabe: Neue Verbindungsstruktur, sortiert nach aktualisierter Abfahrtszeit

**Hinweis:**  
Diese Methode wurde in der finalen Lösung nicht verwendet, war aber für eine robuste Planung vorgesehen.

---

### `verarbeite_verbindungen()`
**Zweck:**  
Kern-Routing-Algorithmus zur Ermittlung optimaler Zugverbindungen mittels Prioritätswarteschlange (Heap).

**Ablauf:**
- **Initialisierung:** Startzustand (Bahnhof, Abfahrt, kein Zug, 0 Umstiege) wird in die Warteschlange gelegt
- **Schleife:** Iterativ wird der Zustand mit der frühesten Ankunftszeit verarbeitet
- **Verbindungsprüfung:**   
  - Lade Verbindungsdaten (Zug, Zeiten, Zielstation). 
  - Prüfe und passe bei Tageswechsel die Ankunfts-/Abfahrtszeiten an.
  - Prüfe Wartezeiten (Mindest- / Maximalumstiegszeit)
  - Bewertung: Verbindung wird aufgenommen, wenn:
        - is_better: Frühere Ankunftszeit oder gleich frühe Ankunftszeit und weniger Umstiege.
        - within_buffer: Etwas spätere Ankunft (innerhalb    Puffer) und nicht mehr Umstiege.
 
- **Buffer-Logik:**  
  - within_buffer ermöglicht das Auffinden qualitativ gleichwertiger oder besserer Verbindungen, die zeitgleich bzw. etwas später ankommen.
  - Zudem werden durch within_buffer werden in einem Durchlauf insgesamt mehr Routen gefunden (auch zu späteren Uhrzeiten als angegebene departure_time)  

- **Ziel:** Wird bei Ankunft am Zielbahnhof gespeichert, aber nicht weiterverfolgt

---

### `reconstruct_route_details()`
**Zweck:**  
Rekonstruiert vollständige Routen vom Ziel zum Start durch Rückverfolgung der Zustände.

**Vorgehen:**  
- Geht rückwärts durch previous_stop und previous_train
- Nutzt arrival_states zur Ermittlung von Ankunfts- und Abfahrtszeiten.
- Ergänzt Zusatzinfos aus prediction_information.
- Erkennt Umstiege und speichert Zugwechsel.
- Gibt die Route in korrekter Reihenfolge zurück.

---

### `filter_and_sort_routes(all_routes_set)`
**Zweck:**  
Filtert die besten Routen (nach Umstiegen und Ankunft) und gibt sie sortiert zurück.

**Filterkriterien:**  
- Bei identischem Startzug und Ankunftszeit bleibt die Route mit weniger Umstiegen  
- Gruppierung nach erstem Zug (`first_train`)  
- Pro Gruppe:
  - Schnellste Verbindung (früheste Ankunft) wird immer übernommen
  - Weitere Routen nur bei:
    - max. 45 Minuten späterer Ankunft und nicht mehr  Umstiege
    - deutlich späterer Ankunft aber weniger Umstiege

**Rückgabe:**  
Liste von Routen-Tupeln: `(Zielbahnhof, Ankunftszeit, letzter Zug, Anzahl Umstiege)`

**Zweck:**
Wenn zwei Routen mit demselben Startzug existieren, ist die Variante mit späterer Ankunft nur dann sinnvoll, wenn die vorhergesagte Verspätung der früheren Route so hoch sein könnte, dass die spätere dadurch schneller ans Ziel führt.
Bei einer Ankunftszeit-Differenz von über 45 Minuten ist das jedoch eher unwahrscheinlich, sodass in diesem Fall nur die effizientere Route beibehalten wird


---

### `routenplanung()`
**Zweck:**  
Berechnet bis zu **vier optimale Zugverbindungen** von einem Start- zu einem Zielbahnhof.

**Parameter (Auswahl):**
- `source`, `target` – Start/Ziel
- `station_departures` - Dictionary mit Abfahrten für jeden Bahnhof
- `departure_time` - Startzeitpunkt (Uhrzeit) der Reise
- `travel_date` - optionales Datum (Standard: heute)
- `min_transfer_minutes` - minimale Umsteigezeit
- `max_initial_wait_hours`, `max_transfer_wait_hours` - max. erlaubte Wartezeiten bei Start bzw. Umstiegen
- `buffer_minutes`- wie viele Minuten später als die aktuell früheste Ankunftszeit an einem Bahnhof eine Ankunft sein darf, um trotzdem der Warteschlange hinzugefügt zu werden
- `delay_hours`- Zeitverschiebung bei erneutem Versuch 
- `delays` – optionales Delay-Dictionary zur Routenberechnung mit Verspätungen

**Ablauf:**
- Führt bis zu `max_attempts` Suchdurchläufe durch
- In jedem Durchlauf:
  - Vorbereitung der Datenstrukturen (`arrival_info` & `arrival_states`)
  - Aufruf von `verarbeite_verbindungen()` mit aktuellem Startzeitpunkt
  - Falls keine Route gefunden wurde, liegt dies häufig an einem späten Startzeitpunkt (z.B. 23:00), bei dem am selben Tag keine Verbindungen existieren. In diesem Fall wird ein zweiter Versuch mit mit start_index = 0 durchgeführt – also mit der frühestmöglichen Verbindung des nächsten Tages
  - Filterung via `filter_and_sort_routes()`
  - Wenn <4 Routen gefunden wurden, neuer Versuch mit verzögertem Startzeitpunkt (delay_hours).
- Abbruch, wenn:
  - 4 Routen gefunden
  - Zeitlimit erreicht
  - Max. Versuche erreicht
- Rückgabe: Detaillierte Routen via `reconstruct_route_details()`

---

## Hilfsfunktionen

| Funktion                     | Beschreibung                                              |
|-----------------------------|-----------------------------------------------------------|
| `find_start_index()`        | Findet Startindex für prüfbare Verbindungen               |
| `load_station_departures_pickle()` | Lädt station_departures aus einer Pickle-Datei       |
| `save_station_departures_pickle()` | Speichert station_departures in eine Pickle-Datei   |

---

## Kontakt

Jule
