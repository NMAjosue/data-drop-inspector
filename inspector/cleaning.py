import pandas as pd


def safe_clean_dataframe(df: pd.DataFrame, drop_exact_duplicates: bool = True) -> pd.DataFrame:
    """
    Apply SAFE, non-destructive cleaning steps:
    - Trim column names
    - Strip whitespace in string cells
    - Convert common empty strings to NA
    - Optionally drop exact duplicate rows
    """
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].astype("string")
            out[col] = out[col].str.strip()
            out[col] = out[col].replace(
                {"": pd.NA, "na": pd.NA, "n/a": pd.NA, "null": pd.NA, "none": pd.NA}
            )

    if drop_exact_duplicates:
        out = out.drop_duplicates()

    return out