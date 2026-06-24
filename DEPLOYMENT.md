# MoreyMachine Deployment

MoreyMachine can run online from checked-in demo data. The app does not call the
NBA API at runtime.

## Streamlit Community Cloud

1. Push the repository to GitHub.
2. In Streamlit Community Cloud, create a new app from the repository.
3. Set the main file path to:

```text
src/moreymachine/app/streamlit_app.py
```

4. Use the default Python environment and `requirements.txt`.
5. Deploy.

If full processed data is not present, the app automatically uses
`data/demo/`.

## Hugging Face Spaces

1. Create a new Space with the Streamlit SDK.
2. Connect or upload this repository.
3. Set the app file to:

```text
src/moreymachine/app/streamlit_app.py
```

4. Ensure `requirements.txt` is at the repository root.
5. Start the Space.

The demo Parquet files in `data/demo/` are small enough for repository-backed
deployment.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python scripts/run_app.py
```

To use full data, run the data and model pipeline scripts first. Without full
artifacts, the dashboard defaults to demo mode.
