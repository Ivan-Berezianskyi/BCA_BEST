"""Quick .bin inspector for MAVLink logs.

Usage:
    python -m app.utils.bin_preview data/binaryfiles/your_log.bin
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any

from pymavlink import mavutil


def _format_columns(tag: str, fields: set[str], fmt_by_tag: dict[str, dict[str, Any]]) -> list[str]:
    """Prefer FMT column order when available, then append extra discovered fields."""
    fmt = fmt_by_tag.get(tag)
    if not fmt:
        return sorted(fields)

    raw_columns = fmt.get("Columns", "")
    ordered = [col.strip() for col in raw_columns.split(",") if col.strip()]
    extras = sorted(col for col in fields if col not in ordered)
    return ordered + extras


def _build_column_units(
    tag: str,
    columns: list[str],
    fmt_by_tag: dict[str, dict[str, Any]],
    fmtu_by_type: dict[int, dict[str, Any]],
    unit_label_by_id: dict[int, str],
    mult_value_by_id: dict[int, float],
) -> dict[str, dict[str, Any]]:
    """Resolve unit and multiplier metadata for each column of a tag."""
    result: dict[str, dict[str, Any]] = {}

    fmt = fmt_by_tag.get(tag)
    if not fmt:
        return result

    fmt_type = fmt.get("Type")
    if not isinstance(fmt_type, int):
        return result

    fmtu = fmtu_by_type.get(fmt_type)
    if not fmtu:
        return result

    unit_ids = fmtu.get("UnitIds", "")
    mult_ids = fmtu.get("MultIds", "")

    for idx, column in enumerate(columns):
        unit_key = unit_ids[idx] if idx < len(unit_ids) else "-"
        mult_key = mult_ids[idx] if idx < len(mult_ids) else "-"

        unit_value = ""
        mult_value: Any = ""
        if unit_key != "-":
            unit_value = unit_label_by_id.get(ord(unit_key), "")
        if mult_key != "-":
            mult_value = mult_value_by_id.get(ord(mult_key), "")

        result[column] = {
            "unit": unit_value,
            "mult": mult_value,
            "unit_key": unit_key,
            "mult_key": mult_key,
        }

    return result


def preview_bin(file_path: str, max_messages: int = 50000, show_sample: bool = True) -> None:
    """Print message tags and all discovered fields from a .bin file."""
    connection = mavutil.mavlink_connection(file_path, dialect="ardupilotmega")

    fields_by_tag: dict[str, set[str]] = defaultdict(set)
    counts_by_tag: dict[str, int] = defaultdict(int)
    sample_by_tag: dict[str, dict[str, Any]] = {}
    # DataFlash unit metadata is described by FMT/FMTU/UNIT/MULT records.
    fmt_by_tag: dict[str, dict[str, Any]] = {}
    fmtu_by_type: dict[int, dict[str, Any]] = {}
    unit_label_by_id: dict[int, str] = {}
    mult_value_by_id: dict[int, float] = {}

    processed = 0
    while processed < max_messages:
        msg = connection.recv_match(blocking=False)
        if msg is None:
            break

        tag = msg.get_type()
        if tag == "BAD_DATA":
            continue

        msg_dict = msg.to_dict()
        msg_dict.pop("mavpackettype", None)

        if tag == "FMT":
            name = msg_dict.get("Name")
            if isinstance(name, str):
                fmt_by_tag[name] = msg_dict
        elif tag == "FMTU":
            fmt_type = msg_dict.get("FmtType")
            if isinstance(fmt_type, int):
                fmtu_by_type[fmt_type] = msg_dict
        elif tag == "UNIT":
            unit_id = msg_dict.get("Id")
            label = msg_dict.get("Label", "")
            if isinstance(unit_id, int) and isinstance(label, str):
                unit_label_by_id[unit_id] = label
        elif tag == "MULT":
            mult_id = msg_dict.get("Id")
            mult = msg_dict.get("Mult")
            if isinstance(mult_id, int):
                mult_value_by_id[mult_id] = mult

        counts_by_tag[tag] += 1
        fields_by_tag[tag].update(msg_dict.keys())
        if tag not in sample_by_tag:
            sample_by_tag[tag] = msg_dict

        processed += 1

    if not counts_by_tag:
        print("No MAVLink messages found. Check file path or file format.")
        return

    print(f"File: {file_path}")
    print(f"Processed messages: {sum(counts_by_tag.values())}")
    print(f"Unique tags: {len(counts_by_tag)}")
    print("-" * 80)

    for tag in sorted(counts_by_tag.keys()):
        columns = _format_columns(tag, fields_by_tag[tag], fmt_by_tag)
        column_units = _build_column_units(
            tag=tag,
            columns=columns,
            fmt_by_tag=fmt_by_tag,
            fmtu_by_type=fmtu_by_type,
            unit_label_by_id=unit_label_by_id,
            mult_value_by_id=mult_value_by_id,
        )

        print(f"TAG: {tag}")
        print(f"COUNT: {counts_by_tag[tag]}")
        print(f"COLUMNS ({len(columns)}):")
        for column in columns:
            unit_info = column_units.get(column)
            if unit_info:
                unit = unit_info["unit"] or "UNKNOWN"
                mult = unit_info["mult"]
                print(f"  - {column}: unit={unit!r}, mult={mult!r}")
            else:
                print(f"  - {column}: unit='UNKNOWN', mult='UNKNOWN'")

        if show_sample:
            sample = sample_by_tag[tag]
            sample_str = ", ".join(
                f"{col}={sample.get(col)!r}" for col in columns
            )
            print(f"SAMPLE: {sample_str}")

        print("-" * 80)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview MAVLink .bin contents: tags and all columns."
    )
    parser.add_argument("file", help="Path to .bin file")
    parser.add_argument(
        "--max-messages",
        type=int,
        default=50000,
        help="Maximum messages to scan (default: 5000)",
    )
    parser.add_argument(
        "--no-sample",
        action="store_true",
        help="Do not print sample row values for each tag",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    preview_bin(
        file_path=args.file,
        max_messages=args.max_messages,
        show_sample=not args.no_sample,
    )


if __name__ == "__main__":
    main()
