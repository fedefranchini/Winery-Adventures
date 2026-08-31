import polars as pl
import pytest

from winery_adventures.io import read_sensors, read_tank_info, write_output
from winery_adventures.validation import DataValidationError


def test_read_sensors_validates_input(tmp_path, sensors_df):
    path = tmp_path / "sensors.tsv"
    sensors_df.write_csv(path, separator="\t")

    assert read_sensors(str(path)).equals(sensors_df)


def test_read_sensors_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="Sensor data file not found"):
        read_sensors(str(tmp_path / "missing.tsv"))


def test_read_sensors_rejects_invalid_schema(tmp_path):
    path = tmp_path / "invalid-sensors.tsv"
    pl.DataFrame({"tank_id": [1], "pH": [3.4]}).write_csv(path, separator="\t")

    with pytest.raises(DataValidationError, match="missing required columns"):
        read_sensors(str(path))


def test_read_sensors_rejects_empty_file(tmp_path):
    # Un file esistente ma privo di contenuto deve produrre un errore applicativo.
    path = tmp_path / "empty-sensors.tsv"
    path.write_text("")

    with pytest.raises(DataValidationError, match="Unable to read Sensor data"):
        read_sensors(str(path))


def test_read_tank_info_validates_and_splits_varieties(tmp_path, tank_info_df):
    path = tmp_path / "tank-info.tsv"
    tank_info_df.write_csv(path, separator="\t")

    result = read_tank_info(str(path))

    assert result.schema["grape_variety"] == pl.List(pl.String)


def test_write_output_writes_csv(tmp_path, sensors_df):
    # Rilegge il file per verificare che la scrittura conservi tutti i dati.
    path = tmp_path / "result.csv"

    write_output(sensors_df, str(path))

    assert pl.read_csv(path).equals(sensors_df)


def test_write_output_reports_unwritable_path(tmp_path, sensors_df):
    # La directory padre non viene creata automaticamente dalla funzione di output.
    path = tmp_path / "missing-directory" / "result.csv"

    with pytest.raises(OSError, match="Unable to write pipeline output"):
        write_output(sensors_df, str(path))
