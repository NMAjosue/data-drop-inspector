import pandas as pd


def build_column_profile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a column-level profiling table.
    """
    rows = []

    for col in df.columns:
        s = df[col]
        null_rate = float(s.isna().mean())
        unique_count = int(s.nunique(dropna=True))
        cardinality = float(unique_count / len(df)) if len(df) else 0.0

        min_val = ""
        max_val = ""
        if pd.api.types.is_numeric_dtype(s):
            try:
                min_val = s.min(skipna=True)
                max_val = s.max(skipna=True)
            except Exception:
                pass
        elif pd.api.types.is_datetime64_any_dtype(s):
            try:
                min_val = s.min(skipna=True)
                max_val = s.max(skipna=True)
            except Exception:
                pass

        rows.append(
            {
                "column": str(col),
                "dtype": str(s.dtype),
                "null_%": round(null_rate * 100, 2),
                "unique_values": unique_count,
                "cardinality": round(cardinality, 3),
                "min": min_val,
                "max": max_val,
            }
        )

    return pd.DataFrame(rows)