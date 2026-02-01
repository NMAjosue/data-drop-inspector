import re
import pandas as pd

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def looks_like_email_column(col_name: str) -> bool:
    name = col_name.strip().lower()
    return ("email" in name) or (name.endswith("_mail")) or (name.endswith("mail"))


def looks_like_date_column(col_name: str) -> bool:
    name = col_name.strip().lower()
    keywords = ["date", "fecha", "datetime", "timestamp", "created", "updated"]
    return any(k in name for k in keywords)


def looks_like_numeric_column(col_name: str) -> bool:
    name = col_name.strip().lower()
    keywords = ["price", "amount", "importe", "total", "qty", "quantity", "units", "discount", "pct", "percent", "%"]
    return any(k in name for k in keywords)


def infer_mixed_types(series: pd.Series, sample_size: int = 200) -> bool:
    s = series.dropna()
    if s.empty:
        return False
    sample = s.sample(min(sample_size, len(s)), random_state=42)
    types = {type(x).__name__ for x in sample.tolist()}
    return len(types) > 1


def detect_issues(df: pd.DataFrame, profile_rows: list[dict]) -> list[dict]:
    """
    Return a list of issues with severity/title/details/suggestion.
    """
    issues = []

    # Potential PK candidates
    pk_candidates = [
        r["column"] for r in profile_rows
        if r["null_%"] <= 1.0 and r["cardinality"] >= 0.98 and r["unique_values"] > 1
    ]
    if pk_candidates:
        issues.append({
            "severity": "info",
            "title": "Potential primary key columns detected",
            "details": f"Almost-unique with low nulls: {', '.join(pk_candidates)}",
            "suggestion": "Use one as a primary key (or combine multiple columns if needed).",
        })

    # Duplicate rows
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        issues.append({
            "severity": "warning",
            "title": "Duplicate rows detected",
            "details": f"Found {dup_count} exact duplicate rows.",
            "suggestion": "Inspect duplicates; deduplicate or define a reliable key strategy.",
        })

    # High null columns
    high_null_cols = [(r["column"], r["null_%"]) for r in profile_rows if r["null_%"] >= 20.0]
    if high_null_cols:
        formatted = ", ".join([f"{c} ({n}%)" for c, n in sorted(high_null_cols, key=lambda x: -x[1])])
        issues.append({
            "severity": "warning",
            "title": "High missing values",
            "details": f"Columns with ≥20% nulls: {formatted}",
            "suggestion": "Decide whether to impute, drop, or treat as optional. Validate upstream source if unexpected.",
        })

    # Mixed types
    mixed_cols = []
    for col in df.columns:
        try:
            if infer_mixed_types(df[col]):
                mixed_cols.append(str(col))
        except Exception:
            pass
    if mixed_cols:
        issues.append({
            "severity": "critical",
            "title": "Mixed types detected",
            "details": f"Columns likely contain mixed Python types: {', '.join(mixed_cols)}",
            "suggestion": "Standardize formats and cast types. Mixed-type columns frequently break pipelines.",
        })

    # Email checks
    issues.extend(detect_email_issues(df))

    # Date parsing checks
    issues.extend(detect_date_parse_issues(df))

    # Numeric-as-text checks
    issues.extend(detect_numeric_as_text_issues(df))

    return issues


def detect_email_issues(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.columns:
        if not looks_like_email_column(str(col)):
            continue
        s = df[col].dropna()
        if s.empty:
            continue

        s_str = s.astype("string").str.strip()
        sample = s_str.sample(min(2000, len(s_str)), random_state=42)
        invalid_mask = ~sample.fillna("").str.match(EMAIL_REGEX)
        invalid_rate = float(invalid_mask.mean())

        if invalid_rate >= 0.05:
            issues.append({
                "severity": "warning",
                "title": f"Invalid emails in `{col}`",
                "details": f"~{round(invalid_rate * 100, 2)}% of sampled values look invalid.",
                "suggestion": "Trim whitespace and validate formatting upstream. Consider rejecting invalid addresses at ingestion.",
            })
    return issues


def detect_date_parse_issues(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.columns:
        if not looks_like_date_column(str(col)):
            continue

        s = df[col].dropna()
        if s.empty:
            continue

        if pd.api.types.is_datetime64_any_dtype(df[col]):
            continue

        s_str = s.astype("string").str.strip()
        sample = s_str.sample(min(2000, len(s_str)), random_state=42)

        parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True, dayfirst=True)
        fail_rate = float(parsed.isna().mean())

        date_like = sample.str.contains(r"[-/:\.]", regex=True).mean()
        if date_like >= 0.4 and fail_rate >= 0.2:
            issues.append({
                "severity": "warning",
                "title": f"Date parsing issues in `{col}`",
                "details": f"~{round(fail_rate * 100, 2)}% of sampled values failed parsing.",
                "suggestion": "Standardize dates (ISO 8601). Avoid mixing formats and ensure consistent timezone handling.",
            })
    return issues


def detect_numeric_as_text_issues(df: pd.DataFrame) -> list[dict]:
    issues = []
    currency_symbols = ["€", "$", "£"]

    for col in df.columns:
        if not looks_like_numeric_column(str(col)):
            continue

        s = df[col].dropna()
        if s.empty:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            continue

        s_str = s.astype("string").str.strip()
        sample = s_str.sample(min(2000, len(s_str)), random_state=42)

        has_currency = any(sample.str.contains(re.escape(sym), regex=True).mean() > 0.05 for sym in currency_symbols)
        has_percent = sample.str.contains("%", regex=False).mean() > 0.05
        has_eu_number = (
            sample.str.contains(r"\d{1,3}(\.\d{3})+(,\d{1,2})?$", regex=True).mean() > 0.10
            or sample.str.contains(r"\d+,\d{1,2}$", regex=True).mean() > 0.10
        )

        cleaned = sample
        for sym in currency_symbols:
            cleaned = cleaned.str.replace(sym, "", regex=False)
        cleaned = cleaned.str.replace("%", "", regex=False)
        cleaned = cleaned.str.replace(" ", "", regex=False)
        cleaned = cleaned.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)

        coerced = pd.to_numeric(cleaned, errors="coerce")
        success = float(coerced.notna().mean())

        if success >= 0.6 and (has_currency or has_percent or has_eu_number):
            hints = []
            if has_currency:
                hints.append("currency symbols")
            if has_percent:
                hints.append("percent signs")
            if has_eu_number:
                hints.append("EU number formatting")

            issues.append({
                "severity": "warning",
                "title": f"Numeric-as-text in `{col}`",
                "details": f"Detected {', '.join(hints)}. ~{round(success * 100, 2)}% could be parsed after cleaning.",
                "suggestion": "Normalize symbols/separators and cast to numeric types to avoid downstream bugs.",
            })

    return issues