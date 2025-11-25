import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import datetime
from typing import List, Tuple, Dict, Any

DATETIME_FMT = "%Y-%m-%d %H:%M"

RE_FLIGHT_ID = re.compile(r"^[A-Za-z0-9]{2,8}$")
RE_AIRPORT = re.compile(r"^[A-Z]{3}$")


def parse_datetime(s: str):
    try:
        return datetime.strptime(s, DATETIME_FMT)
    except Exception:
        return None


def validate_row(cells: List[str]) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Validate a CSV row (list of cells).

    Returns (is_valid, record_dict, errors_list)
    """
    errors = []
    if len(cells) < 6:
        return False, {}, ["missing required fields"]

    flight_id, origin, destination, dep_s, arr_s, price_s = [c.strip() for c in cells[:6]]

    # presence checks
    if not flight_id:
        errors.append("missing flight_id")
    if not origin:
        errors.append("missing origin field")
    if not destination:
        errors.append("missing destination field")
    if not dep_s:
        errors.append("missing departure_datetime")
    if not arr_s:
        errors.append("missing arrival_datetime")
    if not price_s:
        errors.append("missing price")

    # flight_id
    if flight_id and not RE_FLIGHT_ID.match(flight_id):
        if len(flight_id) < 2 or len(flight_id) > 8:
            errors.append("flight_id length must be 2-8 alphanumeric characters")
        else:
            errors.append("invalid flight_id format")

    # origin/destination codes
    if origin and not RE_AIRPORT.match(origin):
        errors.append("invalid origin code")
    if destination and not RE_AIRPORT.match(destination):
        errors.append("invalid destination code")

    # datetimes
    dep_dt = parse_datetime(dep_s) if dep_s else None
    arr_dt = parse_datetime(arr_s) if arr_s else None
    if dep_s and not dep_dt:
        errors.append("invalid departure datetime")
    if arr_s and not arr_dt:
        errors.append("invalid arrival datetime")
    if dep_dt and arr_dt and arr_dt <= dep_dt:
        errors.append("arrival before or equal to departure")

    # price
    price = None
    if price_s:
        try:
            price = float(price_s)
            if price <= 0:
                errors.append("negative or zero price value")
        except Exception:
            errors.append("invalid price format")

    if errors:
        return False, {}, errors

    record = {
        "flight_id": flight_id,
        "origin": origin,
        "destination": destination,
        "departure_datetime": dep_dt.strftime(DATETIME_FMT),
        "arrival_datetime": arr_dt.strftime(DATETIME_FMT),
        "price": round(price, 2),
    }
    return True, record, []


def parse_csv_file(path: str) -> Tuple[List[Dict[str, Any]], List[Tuple[int, str, str]]]:
    """Parse a single CSV file.

    Returns (valid_records, errors) where errors is list of (line_no, raw_line, message)
    """
    valids = []
    errors = []
    with open(path, "r", encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line.strip():
                # ignore blank lines (not included in errors)
                continue
            if line.lstrip().startswith("#"):
                errors.append((i, line, "comment line, ignored for data parsing"))
                continue
            # split respecting CSV commas - use csv.reader on the single line
            try:
                cells = next(csv.reader([line]))
            except Exception:
                errors.append((i, line, "malformed CSV line"))
                continue
            # header detection
            if len(cells) >= 1 and cells[0].strip().lower() == "flight_id":
                # header - skip without reporting
                continue

            valid, record, msgs = validate_row(cells)
            if valid:
                valids.append(record)
            else:
                errors.append((i, line, ", ".join(msgs)))

    return valids, errors


def parse_folder(folder: str) -> Tuple[List[Dict[str, Any]], List[Tuple[str, int, str, str]]]:
    """Parse all .csv files in a folder. Returns combined valids and errors with filename."""
    all_valids = []
    all_errors: List[Tuple[str, int, str, str]] = []
    for path in sorted(glob.glob(os.path.join(folder, "*.csv"))):
        v, e = parse_csv_file(path)
        all_valids.extend(v)
        for (ln, raw, msg) in e:
            all_errors.append((path, ln, raw, msg))
    return all_valids, all_errors


def write_db_json(records: List[Dict[str, Any]], out_path: str):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def write_errors(errors: List[Tuple], out_path: str):
    with open(out_path, "w", encoding="utf-8") as f:
        for err in errors:
            # err can be (line, raw, msg) or (path, line, raw, msg)
            if len(err) == 3:
                ln, raw, msg = err
                f.write(f"Line {ln}: {raw} → {msg}\n")
            else:
                path, ln, raw, msg = err
                f.write(f"{os.path.basename(path)}:Line {ln}: {raw} → {msg}\n")


def load_json_db(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON DB must be a list of flight objects")
    return data


def match_query(db: List[Dict[str, Any]], query: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    # pre-parse query datetimes
    q_dep = parse_datetime(query.get("departure_datetime")) if query.get("departure_datetime") else None
    q_arr = parse_datetime(query.get("arrival_datetime")) if query.get("arrival_datetime") else None
    q_price = float(query.get("price")) if query.get("price") is not None else None

    for rec in db:
        ok = True
        # exact matches
        for key in ("flight_id", "origin", "destination"):
            if key in query:
                if rec.get(key) != query[key]:
                    ok = False
                    break
        if not ok:
            continue

        # departure >=
        if q_dep:
            r_dep = parse_datetime(rec["departure_datetime"])
            if r_dep < q_dep:
                continue

        # arrival <=
        if q_arr:
            r_arr = parse_datetime(rec["arrival_datetime"])
            if r_arr > q_arr:
                continue

        # price <=
        if q_price is not None:
            if float(rec.get("price", 0)) > q_price:
                continue

        results.append(rec)

    return results


def run_queries(db: List[Dict[str, Any]], query_path: str, studentid: str, name: str, lastname: str) -> str:
    with open(query_path, "r", encoding="utf-8") as f:
        qs = json.load(f)
    if isinstance(qs, dict):
        qs = [qs]

    responses = []
    for q in qs:
        matches = match_query(db, q)
        responses.append({"query": q, "matches": matches})

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = name.replace(" ", "_")
    safe_last = lastname.replace(" ", "_")
    fname = f"response_{studentid}_{safe_name}_{safe_last}_{ts}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(responses, f, indent=2, ensure_ascii=False)
    return fname


def main():
    parser = argparse.ArgumentParser(description="Flight schedule parser and query tool")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", help="Path to a CSV file to parse")
    group.add_argument("-d", help="Path to a folder containing .csv files to parse")
    parser.add_argument("-o", help="Output path for valid flights JSON (default: db.json)")
    parser.add_argument("-j", help="Load existing JSON database instead of parsing CSVs")
    parser.add_argument("-q", help="Execute queries from a JSON file on the loaded database")
    parser.add_argument("--studentid", help="Student ID for response filename", default="000000")
    parser.add_argument("--name", help="Given name for response filename", default="Firstname")
    parser.add_argument("--lastname", help="Last name for response filename", default="Lastname")

    args = parser.parse_args()

    out_db_path = args.o if args.o else "db.json"

    db_records: List[Dict[str, Any]] = []
    all_errors: List[Tuple] = []

    if args.j:
        # load existing JSON database
        try:
            db_records = load_json_db(args.j)
        except Exception as e:
            print(f"Failed to load JSON DB: {e}")
            sys.exit(2)
    else:
        # parse CSV(s)
        if args.i:
            if not os.path.exists(args.i):
                print(f"CSV file not found: {args.i}")
                sys.exit(2)
            v, e = parse_csv_file(args.i)
            db_records = v
            # convert errors to include filename
            all_errors = [(args.i, ln, raw, msg) for (ln, raw, msg) in e]
        elif args.d:
            if not os.path.isdir(args.d):
                print(f"Directory not found: {args.d}")
                sys.exit(2)
            v, e = parse_folder(args.d)
            db_records = v
            all_errors = e
        else:
            parser.print_help()
            sys.exit(0)

    # Write db.json
    try:
        write_db_json(db_records, out_db_path)
        print(f"Wrote {len(db_records)} valid records to {out_db_path}")
    except Exception as e:
        print(f"Failed to write DB JSON: {e}")
        sys.exit(3)

    # Write errors.txt
    try:
        write_errors(all_errors, "errors.txt")
        print(f"Wrote {len(all_errors)} error/info lines to errors.txt")
    except Exception as e:
        print(f"Failed to write errors.txt: {e}")
        sys.exit(4)

    # Run queries if requested
    if args.q:
        if not os.path.exists(args.q):
            print(f"Query file not found: {args.q}")
            sys.exit(2)
        try:
            fname = run_queries(db_records, args.q, args.studentid, args.name, args.lastname)
            print(f"Wrote query response to {fname}")
        except Exception as e:
            print(f"Failed to run queries: {e}")
            sys.exit(5)


if __name__ == "__main__":
    main()
