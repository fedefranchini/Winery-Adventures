#!/usr/bin/env python3

"""Generate synthetic tank information and readings into the two data TSV files.

The CLI seed makes generation reproducible. The importable functions use the
state of ``random``: the caller can initialize it with ``random.seed``.
"""

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


def parse_args():
    """Read the command-line options.

    Returns:
        The namespace with seed, number of tanks, readings, and start date.

    Raises:
        SystemExit: if help is requested or an argument is invalid.
    """
    parser = argparse.ArgumentParser(description="Generate test data for Winery Adventures.")
    parser.add_argument("--seed", type=int, default=None, help="Seed for reproducibility.")
    parser.add_argument("--num-tanks", type=int, default=100, help="number of tanks generated")
    parser.add_argument("--num-readings", type=int, default=100_000, help="number of readings generated")
    parser.add_argument("--start-date", type=str, default="2025-01-01", help="start date")
    return parser.parse_args()


def generate_variety_pool(num_varieties=500):
    """Create unique labels by combining a grape variety with an adjective.

    Args:
        num_varieties: maximum number of labels requested.

    Returns:
        The sorted list of labels obtained. May be shorter than requested
        because the search stops after a limited number of attempts.
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
    """Generate tanks with three varieties and a capacity between 1,000 and 1,800 liters.

    Args:
        num_tanks: number of tanks to generate, with identifiers starting at 1.
        variety_list: available labels; a pool is generated if omitted. Must
            contain at least three distinct elements.

    Returns:
        A list of dictionaries with ``tank_id``, ``grape_variety`` (a
        comma-separated string), and ``capacity_liters``.

    Raises:
        ValueError: if the pool does not contain at least three sampleable elements.
    """
    if variety_list is None:
        variety_list = generate_variety_pool(500)

    rows = []
    for tank_id in range(1, num_tanks + 1):
        grape_variety = random.sample(variety_list, k=3)
        capacity = random.randint(1000, 1800)
        rows.append({"tank_id": tank_id, "grape_variety": ",".join(grape_variety), "capacity_liters": capacity})
    return rows


def generate_sensor_data(num_tanks=5, num_readings=20, start_date="2025-01-01", *, n_jobs=-1, show_progress=True):
    """Generate synthetic readings in parallel, preserving their order.

    Args:
        num_tanks: positive number of tanks to assign readings to.
        num_readings: number of readings to generate.
        start_date: start date in ``YYYY-MM-DD`` format; each reading adds
            0 to 10 days and 0 to 23 hours.
        n_jobs: Joblib worker count; -1 uses all available CPUs, 1 is sequential.
        show_progress: display the progress bar when true.

    Returns:
        A list of dictionaries with ``tank_id``, ``time``, ``pH`` (3-4),
        ``temp`` (22-28), and ``quantity_liters`` (200-1,000). The quantity
        is left null with a 10% probability.

    Raises:
        ValueError: if the date is invalid or readings are requested without
            at least one tank.
    """
    base_date = datetime.strptime(start_date, "%Y-%m-%d")

    def generate_sensor_row(row_seed):
        """Create a reading using a worker-private random state."""
        rng = random.Random(row_seed)
        tank_id = rng.randint(1, num_tanks)
        offset_days = rng.randint(0, 10)
        offset_hours = rng.randint(0, 23)
        timestamp = base_date + timedelta(days=offset_days, hours=offset_hours)

        pH = round(rng.uniform(3.0, 4.0), 2)
        temp = round(rng.uniform(22.0, 28.0), 2)
        quantity = rng.randint(200, 1000)
        # Simulate a missing volume reading without changing pH or temperature.
        if rng.randint(1, 10) == 2:
            quantity = None

        return {
            "tank_id": tank_id,
            "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "pH": pH,
            "temp": temp,
            "quantity_liters": quantity,
        }

    # Seeds are set before parallel execution: worker order does not change the data.
    row_seeds = [random.randint(0, 2**32 - 1) for _ in range(num_readings)]

    rows = joblib.Parallel(n_jobs=n_jobs)(
        joblib.delayed(generate_sensor_row)(row_seeds[i])
        for i in tqdm.tqdm(range(num_readings), desc="Generating sensor data", disable=not show_progress)
    )

    return rows


def main():
    """Generate and write ``data/full_tank_info.tsv`` and ``data/full_sensors.tsv``.

    The parameters are read from the CLI and any existing destination files
    are overwritten.

    Raises:
        SystemExit: if the CLI arguments are invalid or help is requested.
        ValueError: if the parameters do not allow generating the readings.
        OSError: if the output directory or files are not writable.
    """
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    variety_pool = generate_variety_pool(num_varieties=500)

    tank_info = generate_tank_info(num_tanks=args.num_tanks, variety_list=variety_pool)
    sensors = generate_sensor_data(num_tanks=args.num_tanks, num_readings=args.num_readings, start_date=args.start_date)

    output_path = Path("data")
    output_path.mkdir(exist_ok=True)

    pl.DataFrame(tank_info, schema=["tank_id", "grape_variety", "capacity_liters"]).write_csv(
        output_path / "full_tank_info.tsv", separator="\t"
    )
    pl.DataFrame(sensors, schema=["tank_id", "time", "pH", "temp", "quantity_liters"]).write_csv(
        output_path / "full_sensors.tsv", separator="\t"
    )

    print(
        f"Generated 'data/full_tank_info.tsv' (with {len(tank_info)} rows) "
        f"and 'data/full_sensors.tsv' (with {len(sensors)} rows)."
    )


if __name__ == "__main__":
    main()
