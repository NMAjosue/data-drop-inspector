import json
import streamlit as st
import pandas as pd

from inspector.io import load_dataset
from inspector.cleaning import safe_clean_dataframe
from inspector.profiling import build_column_profile
from inspector.rules import detect_issues


# -----------------------------
# App config
# -----------------------------
st.set_page_config(page_title="Data Drop Inspector", layout="wide")

# Constrain width + improve vertical rhythm (biggest "pro" win)
st.markdown(
    """
    <style>
        .block-container {
            max-width: 1100px;
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📦 Data Drop Inspector")
st.caption("Upload a dataset and run an inspection to generate a fast data health report.")


# -----------------------------
# Session state
# -----------------------------
for key in ["df", "profile_df", "issues", "report", "cleaned_df", "filename"]:
    if key not in st.session_state:
        st.session_state[key] = None


# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.header("Controls")
    uploaded_file = st.file_uploader("Upload CSV / XLSX", type=["csv", "xlsx"])

    drop_dups = st.toggle("Safe clean: drop exact duplicates", value=True)
    run = st.button("🔎 Run inspection", type="primary", use_container_width=True)

    st.caption("Tip: use the demo file to trigger all checks.")


# -----------------------------
# Load (for preview even before inspection)
# -----------------------------
if uploaded_file:
    try:
        df = load_dataset(uploaded_file)
        if df.empty:
            st.warning("The file loaded successfully, but the dataset is empty.")
        else:
            st.session_state.df = df
            st.session_state.filename = uploaded_file.name
    except Exception as e:
        st.error(f"Error loading file: {e}")


# -----------------------------
# Run inspection
# -----------------------------
if run:
    if st.session_state.df is None:
        st.warning("Upload a file first.")
    else:
        with st.spinner("Running inspection..."):
            df = st.session_state.df

            profile_df = build_column_profile(df)
            profile_rows = profile_df.to_dict(orient="records")
            issues = detect_issues(df, profile_rows)

            report = {
                "dataset": {
                    "rows": int(df.shape[0]),
                    "columns": int(df.shape[1]),
                    "missing_cells_total": int(df.isna().sum().sum()),
                    "duplicate_rows_total": int(df.duplicated().sum()),
                },
                "profile": profile_rows,
                "issues": issues,
            }

            st.session_state.profile_df = profile_df
            st.session_state.issues = issues
            st.session_state.report = report
            st.session_state.cleaned_df = safe_clean_dataframe(df, drop_exact_duplicates=drop_dups)


# -----------------------------
# Main content
# -----------------------------
if st.session_state.df is None:
    st.info("Upload a file from the sidebar to get started.")
    st.stop()

df = st.session_state.df
filename = st.session_state.filename or "uploaded file"

# Section header + calmer hierarchy
st.markdown("### Dataset overview")
st.caption(f"`{filename}`")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Rows", df.shape[0])
m2.metric("Columns", df.shape[1])
m3.metric("Missing cells", int(df.isna().sum().sum()))
m4.metric("Exact duplicates", int(df.duplicated().sum()))

tabs = st.tabs(["Overview", "Column Health", "Issues", "Exports"])


# -----------------------------
# Overview tab
# -----------------------------
with tabs[0]:
    st.markdown("### Preview")
    st.dataframe(df.head(25), use_container_width=True)

    st.markdown("---")
    st.markdown("### Quick notes")
    st.write("Use **Run inspection** to compute profiling and detect common quality issues.")


# -----------------------------
# Column Health tab
# -----------------------------
with tabs[1]:
    if st.session_state.profile_df is None:
        st.info("Run inspection to generate the Column Health table.")
    else:
        st.markdown("### Column Health")
        st.caption("Sorted by missingness (null %) to quickly spot risky fields.")

        prof = st.session_state.profile_df.copy().sort_values(by="null_%", ascending=False)

        q = st.text_input("Filter columns (contains)", value="")
        if q.strip():
            prof = prof[prof["column"].str.lower().str.contains(q.strip().lower(), na=False)]

        st.dataframe(prof, use_container_width=True)


# -----------------------------
# Issues tab
# -----------------------------
with tabs[2]:
    if st.session_state.issues is None:
        st.info("Run inspection to see issues & recommendations.")
    else:
        issues = st.session_state.issues

        groups = {"critical": [], "warning": [], "info": []}
        for it in issues:
            sev = it.get("severity", "info")
            if sev not in groups:
                sev = "info"
            groups[sev].append(it)

        c1, c2, c3 = st.columns(3)
        c1.metric("Critical", len(groups["critical"]))
        c2.metric("Warnings", len(groups["warning"]))
        c3.metric("Info", len(groups["info"]))

        st.markdown("---")
        st.markdown("### Critical")
        if not groups["critical"]:
            st.success("No critical issues found.")
        else:
            for it in groups["critical"]:
                st.error(
                    f"**{it['title']}**  \n"
                    f"{it['details']}  \n"
                    f"*Suggestion:* {it['suggestion']}"
                )

        st.markdown("---")
        st.markdown("### Warnings")
        if not groups["warning"]:
            st.success("No warnings found.")
        else:
            for it in groups["warning"]:
                st.warning(
                    f"**{it['title']}**  \n"
                    f"{it['details']}  \n"
                    f"*Suggestion:* {it['suggestion']}"
                )

        st.markdown("---")
        st.markdown("### Info")
        if not groups["info"]:
            st.info("No informational notes.")
        else:
            for it in groups["info"]:
                st.info(
                    f"**{it['title']}**  \n"
                    f"{it['details']}  \n"
                    f"*Suggestion:* {it['suggestion']}"
                )


# -----------------------------
# Exports tab
# -----------------------------
with tabs[3]:
    if st.session_state.report is None or st.session_state.cleaned_df is None:
        st.info("Run inspection to enable downloads.")
    else:
        st.markdown("### Download artifacts")
        st.caption("Export a JSON report and a safely cleaned CSV for downstream work.")

        report_json = json.dumps(st.session_state.report, indent=2, default=str)
        st.download_button(
            "Download report (JSON)",
            data=report_json,
            file_name="data_drop_report.json",
            mime="application/json",
            use_container_width=True,
        )

        cleaned_csv = st.session_state.cleaned_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download cleaned CSV (safe clean)",
            data=cleaned_csv,
            file_name="cleaned_dataset.csv",
            mime="text/csv",
            use_container_width=True,
        )