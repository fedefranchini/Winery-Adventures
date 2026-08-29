#!/usr/bin/env python3

import argparse
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
    "Nobile", "Pregiato", "Antico", "Classico", "Superiore", "Robusto", "Corposo",
    "Vellutato", "Intenso", "Aromatico", "Elegante", "Vivace", "Barricato", "Storico",
    "Aureo", "Dorato", "Rubino", "Ambrato", "Prezioso", "Sublime", "Sapido", "Fruttato",
    "Speziato", "Morbido", "Vigoroso", "Regale", "Generoso", "Opulento", "Solare",
    "Rustico", "Genuino", "Rinomato", "Selezionato", "Raffinato", "Armonico",
    "Balsamico", "Fragrante", "Avvolgente", "Maestoso", "Splendido",
]

# Some examples of grape variety names (Sardinian, Italian and international)
GRAPE_VARIETIES = [
    "Cannonau", "Vermentino", "Bovale", "Carignano", "Monica", "Nuragus", "Nasco",
    "Vernaccia", "Torbato", "Nieddera", "Giro", "Pascale", "Semidano", "Malvasia",
    "Caricagiola", "Sangiovese", "Nebbiolo", "Barbera", "Montepulciano", "Sagrantino",
    "Primitivo", "Negroamaro", "Aglianico", "Dolcetto", "Corvina", "Teroldego",
    "Garganega", "Verdicchio", "Fiano", "Greco", "Falanghina", "Grillo", "Cortese",
    "Arneis", "Trebbiano", "Merlot", "Cabernet", "Syrah", "Grenache", "Tempranillo",
    "Malbec", "Zinfandel", "Chardonnay", "Riesling", "Viognier", "Moscato",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Genera dati di prova per Winery Adventures.")
    parser.add_argument("--seed", type=int, default=None, help="Seed per la riproducibilità.")
    parser.add_argument("--num-tanks", type=int, default=100, help="numero di tanks generato")
    parser.add_argument("--num-readings", type=int, default=100_000, help="numero letture generato")
    parser.add_argument("--start-date", type=str, default="2025-01-01", help="data inizio")
    return parser.parse_args()


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

    return sorted(all_combos)


def generate_tank_info(num_tanks=20, variety_list=None):
    """
    Creates tank_info data with columns:
      tank_id, grape_variety, capacity_liters
    """
    if variety_list is None:
        variety_list = generate_variety_pool(500)

    rows = []
    for tank_id in range(1, num_tanks + 1):
        grape_variety = random.sample(variety_list, k=3)
        capacity = random.randint(1000, 1800)
        rows.append({"tank_id": tank_id, "grape_variety": ",".join(grape_variety), "capacity_liters": capacity})
    return rows


def generate_sensor_data(num_tanks=5, num_readings=20, start_date="2025-01-01"):
    base_date = datetime.strptime(start_date, "%Y-%m-%d")

    def generate_sensor_row(row_seed):
        rng = random.Random(row_seed)
        tank_id = rng.randint(1, num_tanks)
        offset_days = rng.randint(0, 10)
        offset_hours = rng.randint(0, 23)
        timestamp = base_date + timedelta(days=offset_days, hours=offset_hours)

        pH = round(rng.uniform(3.0, 4.0), 2)
        temp = round(rng.uniform(22.0, 28.0), 2)
        quantity = rng.randint(200, 1000)
        if rng.randint(1, 10) == 2:
            quantity = None

        return {
            "tank_id": tank_id,
            "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "pH": pH,
            "temp": temp,
            "quantity_liters": quantity,
        }

    row_seeds = [random.randint(0, 2**32 - 1) for _ in range(num_readings)]

    rows = joblib.Parallel(n_jobs=-1)(
        joblib.delayed(generate_sensor_row)(row_seeds[i])
        for i in tqdm.tqdm(range(num_readings), desc="Generating sensor data")
    )

    return rows


def main():
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    variety_pool = generate_variety_pool(num_varieties=500)

    tank_info = generate_tank_info(num_tanks=args.num_tanks, variety_list=variety_pool)
    sensors = generate_sensor_data(
        num_tanks=args.num_tanks, num_readings=args.num_readings, start_date=args.start_date
    )

    output_path = Path("data")
    output_path.mkdir(exist_ok=True)

    pl.DataFrame(tank_info, schema=["tank_id", "grape_variety", "capacity_liters"]).write_csv(
        output_path / "full_tank_info.tsv", separator="\t"
    )
    pl.DataFrame(sensors, schema=["tank_id", "time", "pH", "temp", "quantity_liters"]).write_csv(
        output_path / "full_sensors.tsv", separator="\t"
    )

    print(f"Generated 'tank_info.tsv' (with {len(tank_info)} rows) and 'sensors.tsv' (with {len(sensors)} rows).")


if __name__ == "__main__":
    main()