#!/usr/bin/env python3

import random
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import polars as pl
import tqdm

# Some examples of descriptive (oenological) adjectives.
# Combined with a grape variety they form the label of a specific
# lot/cuvée, e.g. "CannonauBarricato" or "VermentinoVellutato".
ADJECTIVES = [
    "Nobile",
    "Pregiato",
    "Antico",
    "Classico",
    "Superiore",
    "Robusto",
    "Corposo",
    "Vellutato",
    "Intenso",
    "Aromatico",
    "Elegante",
    "Vivace",
    "Barricato",
    "Storico",
    "Aureo",
    "Dorato",
    "Rubino",
    "Ambrato",
    "Prezioso",
    "Sublime",
    "Sapido",
    "Fruttato",
    "Speziato",
    "Morbido",
    "Vigoroso",
    "Regale",
    "Generoso",
    "Opulento",
    "Solare",
    "Rustico",
    "Genuino",
    "Rinomato",
    "Selezionato",
    "Raffinato",
    "Armonico",
    "Balsamico",
    "Fragrante",
    "Avvolgente",
    "Maestoso",
    "Splendido",
]

# Some examples of grape variety names (Sardinian, Italian and international)
GRAPE_VARIETIES = [
    "Cannonau",
    "Vermentino",
    "Bovale",
    "Carignano",
    "Monica",
    "Nuragus",
    "Nasco",
    "Vernaccia",
    "Torbato",
    "Nieddera",
    "Giro",
    "Pascale",
    "Semidano",
    "Malvasia",
    "Caricagiola",
    "Sangiovese",
    "Nebbiolo",
    "Barbera",
    "Montepulciano",
    "Sagrantino",
    "Primitivo",
    "Negroamaro",
    "Aglianico",
    "Dolcetto",
    "Corvina",
    "Teroldego",
    "Garganega",
    "Verdicchio",
    "Fiano",
    "Greco",
    "Falanghina",
    "Grillo",
    "Cortese",
    "Arneis",
    "Trebbiano",
    "Merlot",
    "Cabernet",
    "Syrah",
    "Grenache",
    "Tempranillo",
    "Malbec",
    "Zinfandel",
    "Chardonnay",
    "Riesling",
    "Viognier",
    "Moscato",
]


def generate_variety_pool(num_varieties=500):
    """
    Creates a set of 'num_varieties' grape variety lot labels, each formed by
    combining a random grape variety with a random adjective,
    e.g., "CannonauBarricato" or "VermentinoVellutato".

    We ensure no duplicates by storing them in a set until we reach
    the desired quantity, or exhaust combinations (whichever comes first).
    """
    all_combos = set()
    max_attempts = num_varieties * 5  # safeguard for random loops

    while len(all_combos) < num_varieties and max_attempts > 0:
        adj = random.choice(ADJECTIVES)
        grape = random.choice(GRAPE_VARIETIES)
        combo = f"{grape}{adj}"
        all_combos.add(combo)
        max_attempts -= 1

    # Convert set to a list and return
    return list(all_combos)


def generate_tank_info(num_tanks=20, variety_list=None):
    """
    Creates tank_info data with columns:
      tank_id, grape_variety, capacity_liters
    - tank_id in [1..num_tanks]
    - grape_variety: a small blend randomly chosen from 'variety_list'
    - capacity_liters: capacity of the fermentation tank (small winery scale)
    """
    if variety_list is None:
        # Default to 500 generated varieties
        variety_list = generate_variety_pool(500)

    rows = []
    for tank_id in range(1, num_tanks + 1):
        grape_variety = random.sample(variety_list, k=3)
        capacity = random.randint(1000, 1800)
        rows.append({"tank_id": tank_id, "grape_variety": ",".join(grape_variety), "capacity_liters": capacity})
    return rows


def generate_sensor_data(num_tanks=5, num_readings=20, start_date="2025-01-01"):
    """
    Creates sensor readings with columns:
      tank_id, time, pH, temp, quantity_liters

    - Randomly picks from 1..num_tanks for tank_id.
    - Time is spread around a given start date with random offsets.
    - pH is in a range of ~3.0 to 4.0 (typical for must/wine)
    - Temp is in a range of ~22 to 28 (typical for red wine fermentation)
    - quantity_liters is the volume of must in the tank, from 200 to 1000
    Returns a list of dict rows.
    """
    base_date = datetime.strptime(start_date, "%Y-%m-%d")

    def generate_sensor_row():
        tank_id = random.randint(1, num_tanks)
        # Generate a random offset (in hours or days) from base_date
        offset_days = random.randint(0, 10)  # up to 10 days after
        offset_hours = random.randint(0, 23)
        timestamp = base_date + timedelta(days=offset_days, hours=offset_hours)

        pH = round(random.uniform(3.0, 4.0), 2)
        temp = round(random.uniform(22.0, 28.0), 2)
        quantity = random.randint(200, 1000)
        quantity_none = random.randint(1, 10) == 2
        if quantity_none:
            quantity = None

        return {
            "tank_id": tank_id,
            "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "pH": pH,
            "temp": temp,
            "quantity_liters": quantity,
        }

    rows = joblib.Parallel(n_jobs=-1)(
        joblib.delayed(generate_sensor_row)() for _ in tqdm.tqdm(range(num_readings), desc="Generating sensor data")
    )

    return rows


def main():
    # For reproducibility, you can fix the random seed:
    # random.seed(42)

    NUM_TANKS = 100
    NUM_READINGS = 100_000

    # Create a big list of grape variety lot labels
    variety_pool = generate_variety_pool(num_varieties=500)

    # Create 'tank_info.tsv'
    tank_info = generate_tank_info(num_tanks=NUM_TANKS, variety_list=variety_pool)
    sensors = generate_sensor_data(num_tanks=NUM_TANKS, num_readings=NUM_READINGS, start_date="2025-01-01")

    output_path = Path("data")
    output_path.mkdir(exist_ok=True)

    # Write tank_info.tsv
    pl.DataFrame(tank_info, schema=["tank_id", "grape_variety", "capacity_liters"]).write_csv(
        output_path / "full_tank_info.tsv", separator="\t"
    )

    # Write sensors.tsv
    pl.DataFrame(sensors, schema=["tank_id", "time", "pH", "temp", "quantity_liters"]).write_csv(
        output_path / "full_sensors.tsv", separator="\t"
    )

    print(f"Generated 'tank_info.tsv' (with {len(tank_info)} rows) and 'sensors.tsv' (with {len(sensors)} rows).")


if __name__ == "__main__":
    main()
