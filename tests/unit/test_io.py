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


def test_read_sensors_accepts_all_null_quantities(tmp_path, sensors_df):
    path = tmp_path / "sensors.tsv"
    sensors_df.with_columns(pl.lit(None).alias("quantity_liters")).write_csv(path, separator="\t")

    result = read_sensors(str(path))

    assert result.schema["quantity_liters"] == pl.Float64
    assert result.get_column("quantity_liters").null_count() == sensors_df.height


def test_read_sensors_rejects_textual_quantities(tmp_path, sensors_df):
    path = tmp_path / "sensors.tsv"
    sensors_df.with_columns(pl.lit("unknown").alias("quantity_liters")).write_csv(path, separator="\t")

    with pytest.raises(DataValidationError, match="requires numeric columns: quantity_liters"):
        read_sensors(str(path))


@pytest.mark.parametrize(
    ("column", "initial_value", "last_value"),
    [("quantity_liters", "", "500"), ("temp", "25", "25.5"), ("pH", "3", "3.5")],
)
def test_read_sensors_infers_numeric_types_from_the_whole_file(tmp_path, column, initial_value, last_value):
    # The value in row 101 must contribute to type inference, not just the first 100 rows.
    path = tmp_path / "sensors.tsv"
    rows = []
    for index in range(101):
        row = {"tank_id": "1", "time": "2025-01-01 00:00:00", "pH": "3.5", "temp": "25", "quantity_liters": "500"}
        row[column] = initial_value if index < 100 else last_value
        rows.append("\t".join(row.values()))
    header = "tank_id\ttime\tpH\ttemp\tquantity_liters\n"
    path.write_text(header + "\n".join(rows), encoding="utf-8")

    result = read_sensors(str(path))

    assert result.height == 101
    assert result.schema[column].is_numeric()
    assert result.get_column(column)[-1] == float(last_value)
    if column == "quantity_liters":
        assert result.get_column(column).null_count() == 100


def test_read_sensors_rejects_text_after_numeric_rows(tmp_path):
    # Scanning the whole file must not convert an invalid textual value to null.
    path = tmp_path / "sensors.tsv"
    header = "tank_id\ttime\tpH\ttemp\tquantity_liters\n"
    valid_row = "1\t2025-01-01 00:00:00\t3.5\t25\t500\n"
    invalid_row = "1\t2025-01-01 00:00:00\t3.5\t25\tunknown\n"
    path.write_text(header + valid_row * 100 + invalid_row, encoding="utf-8")

    with pytest.raises(DataValidationError, match="requires numeric columns: quantity_liters"):
        read_sensors(str(path))


def test_read_tank_info_rejects_late_decimal_capacity(tmp_path):
    # Capacity must remain an integer by contract, even if a decimal appears at the end.
    path = tmp_path / "tank-info.tsv"
    header = "tank_id\tgrape_variety\tcapacity_liters\n"
    rows = [f"{tank_id}\tMerlot\t1200" for tank_id in range(1, 101)]
    rows.append("101\tMerlot\t1200.5")
    path.write_text(header + "\n".join(rows), encoding="utf-8")

    with pytest.raises(DataValidationError, match="requires capacity_liters to be an integer column"):
        read_tank_info(str(path))


def test_read_sensors_rejects_invalid_schema(tmp_path):
    path = tmp_path / "invalid-sensors.tsv"
    pl.DataFrame({"tank_id": [1], "pH": [3.4]}).write_csv(path, separator="\t")

    with pytest.raises(DataValidationError, match="missing required columns"):
        read_sensors(str(path))


def test_read_sensors_rejects_empty_file(tmp_path):
    # An existing file with no content must produce an application error.
    path = tmp_path / "empty-sensors.tsv"
    path.write_text("")

    with pytest.raises(DataValidationError, match="Unable to read Sensor data"):
        read_sensors(str(path))


def test_read_tank_info_validates_and_splits_varieties(tmp_path, tank_info_df):
    path = tmp_path / "tank-info.tsv"
    tank_info_df.write_csv(path, separator="\t")

    result = read_tank_info(str(path))

    assert result.schema["grape_variety"] == pl.List(pl.String)


def test_read_tank_info_trims_each_variety(tmp_path):
    path = tmp_path / "tank-info.tsv"
    pl.DataFrame(
        {
            "tank_id": [1],
            "grape_variety": ["Merlot, Cabernet "],
            "capacity_liters": [1200],
        }
    ).write_csv(path, separator="\t")

    result = read_tank_info(str(path))

    assert result.get_column("grape_variety").to_list() == [["Merlot", "Cabernet"]]


def test_write_output_writes_csv(tmp_path, sensors_df):
    # Read the file back to verify that writing preserves all data.
    path = tmp_path / "result.csv"

    write_output(sensors_df, str(path))

    assert pl.read_csv(path).equals(sensors_df)


def test_write_output_reports_unwritable_path(tmp_path, sensors_df):
    # The output function does not automatically create the parent directory.
    path = tmp_path / "missing-directory" / "result.csv"

    with pytest.raises(OSError, match="Unable to write pipeline output"):
        write_output(sensors_df, str(path))
