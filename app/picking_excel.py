from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile


def _col_letters_to_index(col_str: str) -> int:
    result = 0
    for ch in col_str:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg_rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass(frozen=True)
class Cell:
    value: Any
    text: str


def _read_xls_cells(path: Path) -> dict[str, Cell]:
    import xlrd
    wb = xlrd.open_workbook(str(path))
    sh = wb.sheet_by_index(0)
    cells: dict[str, Cell] = {}
    for row in range(sh.nrows):
        for col in range(sh.ncols):
            address = _col_index_to_letters(col) + str(row + 1)
            raw = sh.cell_value(row, col)
            ctype = sh.cell_type(row, col)
            if ctype == xlrd.XL_CELL_EMPTY:
                continue
            if ctype == xlrd.XL_CELL_DATE:
                dt_tuple = xlrd.xldate_as_tuple(raw, wb.datemode)
                try:
                    value = datetime(*dt_tuple)
                except (ValueError, OverflowError):
                    value = date(1899, 12, 30) + timedelta(days=int(raw))
                text = value.isoformat() if isinstance(value, datetime) else value.isoformat()
            elif ctype == xlrd.XL_CELL_NUMBER:
                if raw == int(raw):
                    value = int(raw)
                else:
                    value = raw
                text = str(value)
            elif ctype == xlrd.XL_CELL_BOOLEAN:
                value = bool(raw)
                text = "TRUE" if value else "FALSE"
            else:
                value = str(raw).strip()
                text = value
            cells[address] = Cell(value=value, text=text)
    return cells


def _col_index_to_letters(index: int) -> str:
    result = ""
    while True:
        result = chr(ord("A") + index % 26) + result
        index = index // 26 - 1
        if index < 0:
            break
    return result


def parse_picking_workbook(path: str | Path) -> list[dict[str, Any]]:
    """Read the KSU picking-list workbook format used by the warehouse."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".xls":
        sheet = _read_xls_cells(p)
    else:
        workbook = _WorkbookReader(p)
        sheet = workbook.first_sheet_cells()

    start_rows = [
        row_number
        for row_number in _used_row_numbers(sheet)
        if _cell_text(sheet, f"P{row_number}") == "PICKING LIST KSU"
    ]
    if not start_rows:
        raise ValueError("Format Excel tidak dikenali. Header PICKING LIST KSU tidak ditemukan.")

    lists_by_id: dict[str, dict[str, Any]] = {}
    last_row = max(_used_row_numbers(sheet))

    for block_index, start in enumerate(start_rows):
        next_start = start_rows[block_index + 1] if block_index + 1 < len(start_rows) else last_row + 1
        picking_id = _clean_picking_id(_cell_text(sheet, f"U{start + 7}") or _cell_text(sheet, f"H{start + 4}"))
        if not picking_id:
            continue

        list_data = lists_by_id.setdefault(
            picking_id,
            {
                "id": picking_id,
                "date": _excel_date_to_iso(_cell_value(sheet, f"U{start + 6}")),
                "noDs": _cell_text(sheet, f"U{start + 8}"),
                "expedition": _cell_text(sheet, f"AK{start + 6}"),
                "plate": _cell_text(sheet, f"AK{start + 7}"),
                "driver": _cell_text(sheet, f"AK{start + 8}"),
                "status": "draft",
                "handover": None,
                "history": [
                    {
                        "at": _now_text(),
                        "by": "System Import",
                        "text": f"Data picking diimpor dari Excel. No Picking List {picking_id}.",
                    }
                ],
                "items": [],
            },
        )

        category = _cell_text(sheet, f"G{start + 10}") or "KSU"
        item_map = {
            f"{item['category']}|{item.get('code', '')}|{item['name']}": item
            for item in list_data["items"]
        }
        current_no_so = ""
        current_dealer_code = ""
        current_dealer = ""

        for row_number in range(start + 13, next_start):
            if _cell_text(sheet, f"C{row_number}").startswith("Nama KSU"):
                break

            current_no_so = _cell_text(sheet, f"E{row_number}") or current_no_so
            current_dealer_code = _cell_text(sheet, f"J{row_number}") or current_dealer_code
            current_dealer = _cell_text(sheet, f"M{row_number}") or current_dealer

            code = _cell_text(sheet, f"Z{row_number}")
            name = _cell_text(sheet, f"AE{row_number}")
            qty_set = _parse_qty(_cell_value(sheet, f"AM{row_number}") or _cell_text(sheet, f"AM{row_number}"))
            qty_pcs = _parse_qty(_cell_value(sheet, f"AP{row_number}") or _cell_text(sheet, f"AP{row_number}"))
            qty = qty_set or qty_pcs
            if not code or not name or qty <= 0:
                continue

            item_key = f"{category}|{code}|{name}"
            item = item_map.get(item_key)
            if item is None:
                item = {
                    "id": _make_item_id(category, code, name),
                    "code": code,
                    "name": name,
                    "category": category,
                    "plannedQty": 0,
                    "actualQty": 0,
                    "confirmed": False,
                    "note": "",
                    "settlements": [],
                    "dealers": [],
                }
                item_map[item_key] = item
                list_data["items"].append(item)

            item["plannedQty"] += qty
            dealer_key = f"{current_no_so}|{current_dealer_code}|{current_dealer}"
            dealer = next((row for row in item["dealers"] if row.get("_key") == dealer_key), None)
            if dealer:
                dealer["qty"] += qty
            else:
                item["dealers"].append(
                    {
                        "_key": dealer_key,
                        "noSo": current_no_so,
                        "code": current_dealer_code,
                        "dealer": current_dealer,
                        "qty": qty,
                    }
                )

    parsed_lists = [row for row in lists_by_id.values() if row["items"]]
    if not parsed_lists:
        raise ValueError("Tidak ada item picking yang berhasil dibaca dari Excel.")

    for list_data in parsed_lists:
        for item in list_data["items"]:
            item["plannedQty"] = _normalize_number(item["plannedQty"])
            item["actualQty"] = _normalize_number(item["actualQty"])
            for dealer in item["dealers"]:
                dealer["qty"] = _normalize_number(dealer["qty"])
                dealer.pop("_key", None)

    return parsed_lists


class _WorkbookReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.archive = ZipFile(path)
        self.shared_strings = self._read_shared_strings()

    def first_sheet_cells(self) -> dict[str, Cell]:
        workbook = ET.fromstring(self.archive.read("xl/workbook.xml"))
        first_sheet = workbook.find("main:sheets/main:sheet", NS)
        if first_sheet is None:
            raise ValueError("Workbook tidak punya sheet.")

        rel_id = first_sheet.attrib[f"{{{NS['rel']}}}id"]
        rels = ET.fromstring(self.archive.read("xl/_rels/workbook.xml.rels"))
        target = ""
        for rel in rels.findall("pkg_rel:Relationship", NS):
            if rel.attrib.get("Id") == rel_id:
                target = rel.attrib["Target"]
                break
        if not target:
            raise ValueError("Relasi sheet tidak ditemukan.")

        sheet_path = f"xl/{target.lstrip('/')}"
        return self._read_sheet_cells(sheet_path)

    def _read_shared_strings(self) -> list[str]:
        try:
            root = ET.fromstring(self.archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return []

        strings: list[str] = []
        for si in root.findall("main:si", NS):
            strings.append("".join(text_node.text or "" for text_node in si.findall(".//main:t", NS)))
        return strings

    def _read_sheet_cells(self, sheet_path: str) -> dict[str, Cell]:
        root = ET.fromstring(self.archive.read(sheet_path))
        cells: dict[str, Cell] = {}
        for cell_node in root.findall(".//main:c", NS):
            address = cell_node.attrib.get("r", "")
            if not address:
                continue
            raw_value = _node_text(cell_node.find("main:v", NS))
            inline = "".join(text_node.text or "" for text_node in cell_node.findall(".//main:is//main:t", NS))
            cell_type = cell_node.attrib.get("t", "")

            if cell_type == "s" and raw_value:
                index = int(float(raw_value))
                text = self.shared_strings[index] if index < len(self.shared_strings) else ""
                value: Any = text
            elif cell_type == "inlineStr":
                text = inline
                value = text
            elif raw_value == "":
                text = inline
                value = inline
            else:
                value = _number_or_text(raw_value)
                text = _format_cell_text(value)

            cells[address] = Cell(value=value, text=unescape(text).strip())
        return cells


def _node_text(node: ET.Element | None) -> str:
    return "" if node is None or node.text is None else node.text


def _number_or_text(value: str) -> Any:
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number


def _format_cell_text(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _used_row_numbers(sheet: dict[str, Cell]) -> list[int]:
    rows = []
    for address in sheet:
        digits = "".join(char for char in address if char.isdigit())
        if digits:
            rows.append(int(digits))
    return sorted(set(rows))


def _cell_text(sheet: dict[str, Cell], address: str) -> str:
    return sheet.get(address, Cell("", "")).text.strip()


def _cell_value(sheet: dict[str, Cell], address: str) -> Any:
    return sheet.get(address, Cell("", "")).value


def _excel_date_to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        serial = int(float(value))
    except (TypeError, ValueError):
        return date.today().isoformat()
    return (date(1899, 12, 30) + timedelta(days=serial)).isoformat()


def _clean_picking_id(value: str) -> str:
    return value.replace("*", "").strip()


def _parse_qty(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return 0


def _normalize_number(value: float | int) -> int | float:
    return int(value) if float(value).is_integer() else value


def _make_item_id(category: str, code: str, name: str) -> str:
    raw = f"{category}-{code}-{name}".lower()
    result = []
    last_dash = False
    for char in raw:
        if char.isalnum():
            result.append(char)
            last_dash = False
        elif not last_dash:
            result.append("-")
            last_dash = True
    return "".join(result).strip("-")


def _now_text() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")
