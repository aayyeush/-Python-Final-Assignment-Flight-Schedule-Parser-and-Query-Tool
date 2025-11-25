# Flight Schedule Parser and Query Tool

This is a small CLI tool to parse flight schedule CSV files, validate records, save valid flights to a JSON database, record parsing errors to `errors.txt`, optionally load an existing JSON database, and run queries from a JSON file.

Usage examples

Parse a single CSV and write `db.json` and `errors.txt`:

```
python flight_parser.py -i data/db.csv
```

Parse all CSVs in a folder:

```
python flight_parser.py -d data/
```

Load an existing JSON DB and run queries:

```
python flight_parser.py -j data/db.json -q data/query.json --studentid 123456 --name John --lastname Doe
```

Options
- `-i path/to/file.csv` : parse a single CSV file
- `-d path/to/folder/` : parse all `.csv` files in a folder
- `-o path/to/output.json` : custom output path for valid flights JSON (default `db.json`)
- `-j path/to/db.json` : load existing JSON database instead of parsing CSVs
- `-q path/to/query.json` : execute queries from a JSON file
- `--studentid`, `--name`, `--lastname` : used to create the response file name (defaults provided)

Outputs
- `db.json` (or custom via `-o`) — valid flights
- `errors.txt` — invalid lines and informative messages
- `response_<studentid>_<name>_<lastname>_<YYYYMMDD_HHMM>.json` — results for queries

Validation rules
- `flight_id`: 2–8 alphanumeric characters
- `origin`, `destination`: 3 uppercase letters
- `departure_datetime`, `arrival_datetime`: valid `YYYY-MM-DD HH:MM`, arrival after departure
- `price`: positive float

See `data/db.csv` and `data/query.json` for sample input files.
# -Python-Final-Assignment-Flight-Schedule-Parser-and-Query-Tool