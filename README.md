cat > README.md << 'EOF'
# Data Drop Inspector

A lightweight **data health inspector** for freelancers and analytics teams: upload a CSV/XLSX, click **Run inspection**, and instantly surface common data quality issues (nulls, duplicates, mixed types, date/email parsing problems, numeric-as-text patterns). Export a JSON report and a safely cleaned CSV.

## Live demo (optional)
If deployed (Streamlit Community Cloud), add your link here.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py