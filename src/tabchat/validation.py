"""CSV validation and dataset card generation for tabchat."""

from __future__ import annotations

import io
from typing import Any
import numpy as np
import pandas as pd

from tabchat.config import get_settings

INT32_MIN = -2_147_483_648
INT32_MAX = 2_147_483_647
FLOAT16_MAX = 65_504.0


import re

class CSVValidationError(ValueError):
    """Raised when an uploaded CSV fails structural or value constraints."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class PIIDetectedError(ValueError):
    """Raised when personally identifiable information (PII) is detected in uploaded table."""

    def __init__(self, detections: list[str]) -> None:
        self.detections = detections
        super().__init__(f"PII detected: {'; '.join(detections)}")


EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b[6-9]\d{9}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
AADHAAR_REGEX = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b")


def _luhn_checksum(card_number_str: str) -> bool:
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) not in (13, 15, 16, 19):
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def screen_for_pii(df: pd.DataFrame, column_names: list[str]) -> None:
    """Screen column names and cell content for obvious personal information.

    Matches emails, phone numbers, SSNs, Aadhaar, and credit card numbers.
    Raises PIIDetectedError if any match is found.
    """
    detections: list[str] = []

    # 1. Screen column names
    pii_keywords = {"email", "ssn", "social_security", "credit_card", "phone_number", "aadhaar", "passport"}
    for col in column_names:
        col_clean = re.sub(r"[^a-zA-Z0-9]", "", col.lower())
        if any(kw.replace("_", "") in col_clean for kw in pii_keywords):
            detections.append(f"Column name '{col}' indicates personal information.")

    # 2. Screen cell values in string/object columns
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s):
            for row_idx, val in enumerate(s):
                if len(detections) >= 5:
                    break
                if pd.isna(val):
                    continue
                str_val = str(val).strip()
                if not str_val:
                    continue

                if EMAIL_REGEX.search(str_val):
                    detections.append(f"Row {row_idx + 1}, Column '{col}': email address pattern detected.")
                    break
                if SSN_REGEX.search(str_val):
                    detections.append(f"Row {row_idx + 1}, Column '{col}': Social Security Number pattern detected.")
                    break
                if AADHAAR_REGEX.search(str_val):
                    detections.append(f"Row {row_idx + 1}, Column '{col}': Aadhaar ID pattern detected.")
                    break
                if PHONE_REGEX.search(str_val):
                    if len(re.sub(r"\D", "", str_val)) >= 10:
                        detections.append(f"Row {row_idx + 1}, Column '{col}': phone number pattern detected.")
                        break
                cc_match = CREDIT_CARD_REGEX.search(str_val)
                if cc_match and _luhn_checksum(cc_match.group(0)):
                    detections.append(f"Row {row_idx + 1}, Column '{col}': credit card number pattern detected.")
                    break

    if detections:
        raise PIIDetectedError(detections)


def _infer_column_type(series: pd.Series) -> str:
    """Infer column type as 'numeric', 'datetime', or 'categorical'."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return "categorical"

    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    # Attempt datetime conversion for object/string columns
    if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
        # Sample non-null to avoid slow conversion on arbitrary strings
        sample = non_null.head(20).astype(str)
        # Avoid treating simple digits or very short tokens as datetimes
        if all(len(s) >= 8 and any(sep in s for sep in ("-", "/", " ", "T")) for s in sample):
            try:
                converted = pd.to_datetime(sample, errors="coerce", format="mixed")
                if converted.notna().all():
                    return "datetime"
            except Exception:
                pass

    return "categorical"


def _sanitize_for_json(val: Any) -> Any:
    """Ensure cell values are JSON serializable (handling NaN, inf, Timestamps)."""
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        if np.isneginf(val) or np.isposinf(val):
            return None
        return float(val)
    if isinstance(val, (pd.Timestamp, np.datetime64)):
        return str(val)
    return str(val)


def validate_and_parse_csv(file_bytes: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate raw CSV bytes against operational boundaries and return DataFrame and Dataset Card.

    Args:
        file_bytes: Raw bytes of the uploaded file.

    Returns:
        (df, dataset_card_dict)

    Raises:
        CSVValidationError: If file violates any structural or content boundaries.
    """
    settings = get_settings()
    errors: list[str] = []

    # 1. Byte size check
    if len(file_bytes) == 0:
        raise CSVValidationError(["Uploaded file is empty (0 bytes)."])
    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise CSVValidationError([
            f"File size {len(file_bytes):,} bytes exceeds maximum allowed limit of {settings.MAX_UPLOAD_BYTES:,} bytes (1 MB)."
        ])

    # 2. Inspect raw header row for duplicates and empty headers
    try:
        text_stream = io.StringIO(file_bytes.decode("utf-8-sig"))
        import csv
        reader = csv.reader(text_stream)
        raw_headers = next(reader, None)
        if raw_headers is None or len(raw_headers) == 0:
            raise CSVValidationError(["File contains no data or could not be parsed as CSV."])
    except UnicodeDecodeError as e:
        raise CSVValidationError([f"File is not valid UTF-8 encoded: {e}"])
    except CSVValidationError:
        raise
    except Exception as e:
        raise CSVValidationError([f"Malformed CSV: {e}"])

    trimmed_headers = [h.strip() for h in raw_headers]
    for idx, h in enumerate(trimmed_headers):
        if not h:
            errors.append(f"Header at column index {idx + 1} is empty or missing a name.")

    seen_headers: set[str] = set()
    for idx, h in enumerate(trimmed_headers):
        if h in seen_headers:
            errors.append(f"Duplicate column header '{h}' found at column index {idx + 1}.")
        else:
            seen_headers.add(h)

    # 3. Parse with pandas UTF-8 (handling BOM)
    try:
        df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8-sig")
    except Exception as e:
        raise CSVValidationError([f"Malformed CSV data: {e}"])

    # Re-assign trimmed column names if column count matches
    if len(df.columns) == len(trimmed_headers):
        df.columns = trimmed_headers

    # 4. Dimension limits
    n_rows = len(df)
    n_cols = len(df.columns)

    if n_rows < 1:
        errors.append("Dataset must contain at least 1 row of data.")
    elif n_rows > settings.MAX_ROWS:
        errors.append(f"Row count {n_rows} exceeds maximum limit of {settings.MAX_ROWS} rows.")

    if n_cols < 2:
        errors.append(f"Column count {n_cols} is below minimum requirement of 2 columns.")
    elif n_cols > settings.MAX_COLS:
        errors.append(f"Column count {n_cols} exceeds maximum limit of {settings.MAX_COLS} columns.")

    # 5. Check 100% null or empty columns
    for col_idx in range(n_cols):
        col_name = trimmed_headers[col_idx] if col_idx < len(trimmed_headers) else f"col_{col_idx}"
        s = df.iloc[:, col_idx]
        if bool(s.isna().all()) or bool((s.astype(str).str.strip() == "").all()):
            errors.append(f"Column '{col_name}' is 100% null or empty.")

    # 6. Cell-level value checks (capped at 20 errors)
    for col_idx in range(n_cols):
        if len(errors) >= 20:
            break
        col = trimmed_headers[col_idx] if col_idx < len(trimmed_headers) else f"col_{col_idx}"
        s = df.iloc[:, col_idx]

        # Check numeric bounds
        if pd.api.types.is_numeric_dtype(s):
            for row_idx, val in enumerate(s):
                if len(errors) >= 20:
                    break
                if pd.isna(val):
                    continue

                # Check float finiteness and float16 range
                if isinstance(val, (float, np.floating)):
                    if not np.isfinite(val):
                        errors.append(f"Row {row_idx + 1}, Column '{col}': non-finite float value ({val}).")
                        continue
                    if abs(val) > FLOAT16_MAX:
                        errors.append(
                            f"Row {row_idx + 1}, Column '{col}': float value {val} exceeds float16 range (|x| <= {FLOAT16_MAX})."
                        )
                        continue

                # Check integer bounds
                if isinstance(val, (int, np.integer)) or (isinstance(val, float) and val.is_integer()):
                    int_val = int(val)
                    if int_val < INT32_MIN or int_val > INT32_MAX:
                        errors.append(
                            f"Row {row_idx + 1}, Column '{col}': integer value {int_val} exceeds signed int32 bounds."
                        )

        # Check string lengths
        else:
            for row_idx, val in enumerate(s):
                if len(errors) >= 20:
                    break
                if pd.isna(val):
                    continue
                str_val = str(val)
                if len(str_val) > settings.MAX_STR_LEN:
                    errors.append(
                        f"Row {row_idx + 1}, Column '{col}': cell length {len(str_val)} chars exceeds limit of {settings.MAX_STR_LEN}."
                    )

    if errors:
        raise CSVValidationError(errors[:20])

    # 7. Screen for Personal Identifiable Information (PII)
    screen_for_pii(df, list(df.columns))

    # 8. Generate Dataset Card
    inferred_types: dict[str, str] = {}
    null_counts: dict[str, int] = {}
    unique_counts: dict[str, int] = {}

    for col in df.columns:
        inferred_types[col] = _infer_column_type(df[col])
        null_counts[col] = int(df[col].isna().sum())
        unique_counts[col] = int(df[col].nunique(dropna=True))

    preview_df = df.head(5)
    preview_rows: list[dict[str, Any]] = [
        {col: _sanitize_for_json(val) for col, val in row.items()}
        for _, row in preview_df.iterrows()
    ]

    dataset_card: dict[str, Any] = {
        "row_count": n_rows,
        "col_count": n_cols,
        "column_names": list(df.columns),
        "inferred_types": inferred_types,
        "null_counts": null_counts,
        "unique_counts": unique_counts,
        "preview_rows": preview_rows,
    }

    return df, dataset_card
