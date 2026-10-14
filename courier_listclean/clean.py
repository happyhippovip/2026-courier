"""Flag and normalize customer, member, and address lists.

Safe fixes are written only to the cleaned copy and listed in the report.
Unclear values stay as they are and are flagged. Nothing here calls a network
or a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_ROWS = 2000
ORIGINAL_ROW_ID = "original_row_id"

DECISION_REASONS = frozenset(
    {
        "exact_duplicate",
        "fuzzy_duplicate",
        "email_invalid",
        "email_comma",
        "email_double_at",
        "email_at_word",
        "plz_not_5_digits",
        "street_spelling",
        "empty_required",
        "phone_unrecognized",
        "inconsistent_case",
    }
)

_HEADER_FIELDS = {
    "name": "name",
    "namen": "name",
    "vollstaendiger name": "name",
    "telefon": "phone",
    "telefonnummer": "phone",
    "phone": "phone",
    "tel": "phone",
    "mobil": "phone",
    "mobile": "phone",
    "e-mail": "email",
    "email": "email",
    "mail": "email",
    "strasse": "street",
    "str.": "street",
    "street": "street",
    "plz": "plz",
    "postleitzahl": "plz",
    "zip": "plz",
    "postal code": "plz",
    "postcode": "plz",
    "ort": "city",
    "stadt": "city",
    "city": "city",
    "wohnort": "city",
}

_TWO_DIGIT_AREA = frozenset({"30", "40", "69", "89"})
_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PLZ_PREFIX = re.compile(r"^[Dd](?:[Ee])?-(\d{5})$")
_PHONE_SEPARATORS = re.compile(r"[\s./()\-–—]+")


class ListCleanError(ValueError):
    """The list cannot be cleaned under the 79 EUR rules."""


@dataclass(frozen=True)
class Finding:
    row: int
    column: str
    reason: str
    before: str
    after: str
    message: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "original_row_id": self.row,
            "row": self.row,
            "column": self.column,
            "reason": self.reason,
            "before": self.before,
            "after": self.after,
            "message": self.message,
        }


@dataclass
class CleanResult:
    headers: list[str]
    rows: list[list[str]]
    findings: list[Finding] = field(default_factory=list)
    row_numbers: list[int] = field(default_factory=list)

    @property
    def decision_count(self) -> int:
        return sum(1 for item in self.findings if item.reason in DECISION_REASONS)


def clean_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    row_numbers: list[int] | None = None,
    max_rows: int = MAX_ROWS,
) -> CleanResult:
    if max_rows < 1:
        raise ListCleanError("max_rows muss mindestens 1 sein.")
    if not headers or not any(cell.strip() for cell in headers):
        raise ListCleanError("Die Datei hat keine Kopfzeile.")
    if len(rows) > max_rows:
        raise ListCleanError(
            f"Die Liste hat {len(rows)} Datenzeilen. "
            f"Das 79-€-Angebot gilt bis {max_rows} Zeilen."
        )
    numbers = list(row_numbers) if row_numbers is not None else list(range(2, len(rows) + 2))
    if len(numbers) != len(rows):
        raise ListCleanError("Zeilennummern passen nicht zur Liste.")

    clean_headers = [" ".join(header.split()) for header in headers]
    width = len(clean_headers)
    fields = [_field_for_header(header) for header in clean_headers]
    hint_header = _hint_header(clean_headers)
    id_header = _id_header(clean_headers)
    required = _required_fields(set(fields))

    findings: list[Finding] = []
    for index, (original, cleaned) in enumerate(zip(headers, clean_headers)):
        if original != cleaned:
            findings.append(
                _finding(
                    1,
                    cleaned,
                    "whitespace",
                    original,
                    cleaned,
                    _cell(index, 1),
                )
            )

    normalized: list[list[str]] = []
    per_row_notes: list[list[str]] = []
    for row, number in zip(rows, numbers):
        cells = _fit(row, width)
        output: list[str] = []
        notes: list[str] = []
        for index, original in enumerate(cells):
            kind = fields[index]
            value, reasons, messages = _normalize_cell(kind, original)
            column = clean_headers[index]
            if kind in required and value.strip() == "":
                reasons = [*reasons, "empty_required"]
                messages["empty_required"] = f"⚠ Pflichtfeld {column} ist leer"
            for reason in reasons:
                findings.append(
                    _finding(
                        number,
                        column,
                        reason,
                        original,
                        value,
                        _cell(index, number),
                        messages.get(reason),
                    )
                )
                if reason in DECISION_REASONS and reason != "inconsistent_case":
                    notes.append(messages.get(reason) or _default_message(reason, original, value))
            output.append(value)
        normalized.append(output)
        per_row_notes.append(notes)

    _mark_duplicates(normalized, numbers, fields, clean_headers, findings, per_row_notes)

    cleaned_rows: list[list[str]] = []
    for output, notes, number in zip(normalized, per_row_notes, numbers):
        hint = " · ".join(_unique(notes))
        cleaned_rows.append([*output, hint, str(number)])

    findings.sort(key=lambda item: (item.row, item.column, item.reason, item.message))
    return CleanResult(
        headers=[*clean_headers, hint_header, id_header],
        rows=cleaned_rows,
        findings=findings,
        row_numbers=numbers,
    )


def _fit(row: list[str], width: int) -> list[str]:
    cells = list(row[:width])
    if len(cells) < width:
        cells.extend([""] * (width - len(cells)))
    return cells


def _field_for_header(header: str) -> str:
    key = " ".join(header.split()).casefold().replace("ß", "ss")
    return _HEADER_FIELDS.get(key, "")


def _hint_header(headers: list[str]) -> str:
    taken = {header.casefold() for header in headers}
    if "hinweis" not in taken:
        return "Hinweis"
    return "Courier_Hinweis"


def _id_header(headers: list[str]) -> str:
    taken = {header.casefold() for header in headers}
    if ORIGINAL_ROW_ID.casefold() not in taken:
        return ORIGINAL_ROW_ID
    return "courier_original_row_id"


def _required_fields(present: set[str]) -> set[str]:
    required: set[str] = set()
    if "name" in present:
        required.add("name")
    if "plz" in present:
        required.add("plz")
        if "street" in present:
            required.add("street")
        if "city" in present:
            required.add("city")
    elif "email" in present and "phone" not in present and "street" not in present:
        required.add("email")
    return required


def _normalize_cell(kind: str, original: str) -> tuple[str, list[str], dict[str, str]]:
    if original.lstrip().startswith("="):
        return original, ["formula_preserved"], {}
    collapsed = " ".join(original.split())
    reasons: list[str] = []
    messages: dict[str, str] = {}
    if kind == "name":
        value, name_reasons = _normalize_name(collapsed)
        reasons.extend(name_reasons)
    elif kind == "phone":
        value, phone_reason, phone_message = _normalize_phone(collapsed)
        if phone_reason:
            reasons.append(phone_reason)
            if phone_message:
                messages[phone_reason] = phone_message
    elif kind == "email":
        value, email_reasons, email_messages = _normalize_email(collapsed)
        reasons.extend(email_reasons)
        messages.update(email_messages)
    elif kind == "plz":
        value, plz_reason, plz_message = _normalize_plz(collapsed)
        if plz_reason:
            reasons.append(plz_reason)
            if plz_message:
                messages[plz_reason] = plz_message
    elif kind == "street":
        value, street_reasons, street_messages = _normalize_street(collapsed)
        reasons.extend(street_reasons)
        messages.update(street_messages)
    elif kind == "city":
        value = title_case_de(collapsed)
    else:
        value = collapsed

    if kind == "street":
        street_name, _house = _split_house_number(collapsed)
        if _inconsistent_title(street_name):
            reasons.append("inconsistent_case")
    elif kind in {"name", "city"} and _inconsistent_title(collapsed):
        reasons.append("inconsistent_case")
    if (
        kind == "email"
        and value == collapsed.lower()
        and collapsed != collapsed.lower()
        and any(ch.isalpha() for ch in collapsed)
    ):
        reasons.append("inconsistent_case")
    if collapsed != original and "whitespace" not in reasons:
        reasons.append("whitespace")
    # A pure case/format change already explains itself. Keep whitespace when
    # spaces were actually removed so the trim is visible in the report.
    return value, _unique(reasons), messages


def _normalize_name(collapsed: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    text = collapsed
    if text.count(",") == 1:
        left, right = [part.strip() for part in text.split(",")]
        if left and right and not any(ch.isdigit() for ch in text):
            text = f"{right} {left}"
            reasons.append("name_comma_order")
    return title_case_de(text), reasons


def _normalize_phone(collapsed: str) -> tuple[str, str | None, str | None]:
    if collapsed == "":
        return "", None, None
    compact = _PHONE_SEPARATORS.sub("", collapsed)
    national = _german_national(compact)
    if national is None:
        return collapsed, "phone_unrecognized", "⚠ Telefonnummer nicht erkannt, unverändert gelassen"
    formatted = _format_german(national)
    if formatted is None:
        return collapsed, "phone_unrecognized", "⚠ Telefonnummer nicht erkannt, unverändert gelassen"
    if formatted == collapsed:
        return formatted, None, None
    return formatted, "phone_normalized", None


def _german_national(compact: str) -> str | None:
    if compact.startswith("+"):
        if not compact[1:].isdigit() or not compact.startswith("+49"):
            return None
        return compact[3:]
    if compact.startswith("0049") and compact[4:].isdigit():
        return compact[4:]
    if compact.startswith("0") and compact[1:].isdigit():
        return compact[1:]
    return None


def _format_german(national: str) -> str | None:
    if not national.isdigit() or not 6 <= len(national) <= 13:
        return None
    if national.startswith("1"):
        prefix_len = 3
    elif national[:2] in _TWO_DIGIT_AREA:
        prefix_len = 2
    else:
        return f"+49 {national}"
    if prefix_len >= len(national):
        return None
    return f"+49 {national[:prefix_len]} {national[prefix_len:]}"


def _normalize_email(collapsed: str) -> tuple[str, list[str], dict[str, str]]:
    if collapsed == "":
        return "", [], {}
    issue = _email_issue(collapsed)
    if issue:
        message = {
            "email_comma": "⚠ ungültig (Komma statt Punkt), Korrektur nur nach deinem OK",
            "email_double_at": "⚠ ungültig (doppeltes @)",
            "email_at_word": "⚠ „(at)“-Schreibweise, bitte bestätigen",
            "email_invalid": "⚠ ungültige E-Mail, bitte prüfen",
        }[issue]
        return collapsed, [issue], {issue: message}
    lowered = collapsed.lower()
    if lowered == collapsed:
        return lowered, [], {}
    return lowered, ["email_normalized"], {
        "email_normalized": "✅ klein geschrieben, Leerzeichen entfernt"
    }


def _email_issue(text: str) -> str | None:
    folded = text.casefold()
    if "(at)" in folded or "(ät)" in folded:
        return "email_at_word"
    if text.count("@") > 1:
        return "email_double_at"
    if "," in text:
        return "email_comma"
    if _EMAIL.fullmatch(text):
        return None
    return "email_invalid"


def _normalize_plz(collapsed: str) -> tuple[str, str | None, str | None]:
    if collapsed == "":
        return "", None, None
    prefixed = _PLZ_PREFIX.fullmatch(collapsed)
    if prefixed:
        return prefixed.group(1), "plz_country_prefix", None
    if re.fullmatch(r"\d{5}", collapsed):
        return collapsed, None, None
    if re.fullmatch(r"\d{4}", collapsed):
        return (
            collapsed,
            "plz_not_5_digits",
            "⚠ PLZ hat nur 4 Stellen (fehlt eine führende 0?). Bitte prüfen, wird nicht geraten",
        )
    return (
        collapsed,
        "plz_not_5_digits",
        "⚠ PLZ hat nicht genau 5 Stellen. Bitte prüfen, wird nicht geraten",
    )


def _normalize_street(collapsed: str) -> tuple[str, list[str], dict[str, str]]:
    if collapsed == "":
        return "", [], {}
    name, house = _split_house_number(collapsed)
    new_name, reasons, messages = _street_name(name)
    if house:
        value = f"{new_name} {house}".strip()
    else:
        value = new_name
    return value, reasons, messages


def _split_house_number(text: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)(?:\s+)?(\d\S*)$", text)
    if not match:
        return text, ""
    name = match.group(1).rstrip()
    house = match.group(2)
    if not name:
        return text, ""
    return name, house


def _street_suffix(name: str, suffix: str) -> str | None:
    """Match an ASCII suffix without expanding ß (casefold turns ß into ss)."""
    lowered = name.lower()
    if len(lowered) != len(name) or not lowered.endswith(suffix):
        return None
    return name[: -len(suffix)]


def _street_name(name: str) -> tuple[str, list[str], dict[str, str]]:
    stem = _street_suffix(name, "sstrasse")
    if stem is not None:
        return (
            _title_stem(stem) + "straße",
            ["street_spelling"],
            {"street_spelling": f"⚠ Schreibweise „{name}“ angepasst, bitte bestätigen"},
        )
    stem = _street_suffix(name, "strasse")
    if stem is not None:
        return (
            _title_stem(stem) + "straße",
            ["street_spelling"],
            {"street_spelling": f"⚠ Schreibweise „{name}“ angepasst, bitte bestätigen"},
        )
    stem = _street_suffix(name, "str.")
    if stem is not None:
        return _finish_abbreviation(stem), ["street_abbreviation"], {}
    stem = _street_suffix(name, "str")
    if stem is not None and len(name) > 3:
        return _finish_abbreviation(stem), ["street_abbreviation"], {}
    return title_case_de(name), [], {}


def _finish_abbreviation(stem: str) -> str:
    titled = _title_stem(stem)
    if titled.endswith("-"):
        return titled + "Straße"
    return titled + "straße"


def _title_stem(stem: str) -> str:
    return title_case_de(stem)


def title_case_de(text: str) -> str:
    def one(token: str) -> str:
        if any(ch.isdigit() for ch in token):
            return token
        parts = token.split("-")
        titled = []
        for part in parts:
            if not part:
                titled.append(part)
                continue
            titled.append(part[0].upper() + part[1:].lower())
        return "-".join(titled)

    return " ".join(one(token) for token in text.split(" "))


def _inconsistent_title(collapsed: str) -> bool:
    """True when a letter-group is not title case. Digits keep suffixes like 5a."""
    for token in collapsed.split():
        if any(ch.isdigit() for ch in token):
            continue
        for part in token.split("-"):
            letters = "".join(ch for ch in part if ch.isalpha())
            if not letters:
                continue
            if letters != letters[0].upper() + letters[1:].lower():
                return True
    return False


def _mark_duplicates(
    rows: list[list[str]],
    numbers: list[int],
    fields: list[str],
    headers: list[str],
    findings: list[Finding],
    notes: list[list[str]],
) -> None:
    name_at = _first_index(fields, "name")
    plz_at = _first_index(fields, "plz")
    exact_groups: dict[tuple[str, ...], list[int]] = {}
    fuzzy_groups: dict[tuple[tuple[str, ...], str], list[int]] = {}
    for index, row in enumerate(rows):
        if not any(cell.strip() for cell in row):
            continue
        exact_groups.setdefault(tuple(row), []).append(index)
        if name_at is None or plz_at is None:
            continue
        name_key = _name_key(row[name_at])
        plz = row[plz_at].strip()
        if not name_key or not plz:
            continue
        fuzzy_groups.setdefault((name_key, plz), []).append(index)

    exact_members = {index for group in exact_groups.values() if len(group) > 1 for index in group}
    name_header = headers[name_at] if name_at is not None else ""

    for group in exact_groups.values():
        if len(group) < 2:
            continue
        _add_duplicate_findings(
            group,
            numbers,
            rows,
            name_at,
            name_header,
            findings,
            notes,
            fuzzy=False,
        )

    for group in fuzzy_groups.values():
        if len(group) < 2:
            continue
        anchor = group[0]
        members = [anchor]
        for index in group[1:]:
            if index in exact_members and tuple(rows[index]) == tuple(rows[anchor]):
                continue
            members.append(index)
        if len(members) < 2:
            continue
        _add_duplicate_findings(
            members,
            numbers,
            rows,
            name_at,
            name_header,
            findings,
            notes,
            fuzzy=True,
        )


def _add_duplicate_findings(
    group: list[int],
    numbers: list[int],
    rows: list[list[str]],
    name_at: int | None,
    name_header: str,
    findings: list[Finding],
    notes: list[list[str]],
    *,
    fuzzy: bool,
) -> None:
    anchor = group[0]
    anchor_row = numbers[anchor]
    other_rows = [numbers[index] for index in group[1:]]
    label = " (Name + PLZ)" if fuzzy else ""
    if len(other_rows) == 1:
        anchor_message = f"Zeile {other_rows[0]} = mögliche Dublette{label} von Zeile {anchor_row}"
    else:
        listed = ", ".join(f"Zeile {number}" for number in other_rows)
        anchor_message = f"{listed} = mögliche Dubletten{label} von Zeile {anchor_row}"
    later_message = (
        "⚠ mögliche Dublette (Name + PLZ), du entscheidest"
        if fuzzy
        else "⚠ Dublette, du entscheidest"
    )
    reason = "fuzzy_duplicate" if fuzzy else "exact_duplicate"
    for position, index in enumerate(group):
        message = anchor_message if position == 0 else later_message
        name_value = rows[index][name_at] if name_at is not None else ""
        findings.append(
            Finding(
                row=numbers[index],
                column=name_header,
                reason=reason,
                before=name_value,
                after=name_value,
                message=message,
            )
        )
        notes[index].append(message)


def _name_key(name: str) -> tuple[str, ...]:
    tokens = [token.casefold() for token in name.split() if token]
    return tuple(sorted(tokens))


def _first_index(fields: list[str], kind: str) -> int | None:
    try:
        return fields.index(kind)
    except ValueError:
        return None


def _cell(column_index: int, row: int) -> str:
    number = column_index + 1
    letters = []
    while number:
        number, rem = divmod(number - 1, 26)
        letters.append(chr(65 + rem))
    return f"{''.join(reversed(letters))}{row}"


def _default_message(reason: str, before: str, after: str) -> str:
    messages = {
        "whitespace": "Leerzeichen bereinigt",
        "inconsistent_case": "Groß-/Kleinschreibung vereinheitlicht",
        "name_comma_order": "Name von „Nachname, Vorname“ nach „Vorname Nachname“ gesetzt",
        "phone_normalized": "Telefon auf +49 gesetzt",
        "email_normalized": "✅ klein geschrieben, Leerzeichen entfernt",
        "plz_country_prefix": "Länderkennzeichen vor der PLZ entfernt",
        "street_abbreviation": "Straßenabkürzung erweitert",
        "formula_preserved": "Formel unverändert gelassen",
        "exact_duplicate": "⚠ Dublette, du entscheidest",
        "fuzzy_duplicate": "⚠ mögliche Dublette (Name + PLZ), du entscheidest",
    }
    return messages.get(reason, reason)


def _finding(
    row: int,
    column: str,
    reason: str,
    before: str,
    after: str,
    cell: str,
    message: str | None = None,
) -> Finding:
    text = message or _default_message(reason, before, after)
    if before != after:
        shown = f'{cell}: "{before}" → "{after}" — {text}'
    else:
        shown = f'{cell}: "{before}" — {text}'
    return Finding(row=row, column=column, reason=reason, before=before, after=after, message=shown)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
