import pandas as pd


def load_dataset(uploaded_file) -> pd.DataFrame:
    """
    Load a CSV or XLSX from a Streamlit UploadedFile-like object.
    Raises an exception if loading fails.
    """
    name = uploaded_file.name.lower().strip()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith(".xlsx"):
        return pd.read_excel(uploaded_file)
    raise ValueError("Unsupported file type. Please upload a CSV or XLSX.")