PY ?= python

install:
	$(PY) -m pip install -e ".[dev]"

ingest:
	$(PY) scripts/ingest_knowledge.py

ingest-bm25:
	$(PY) scripts/ingest_knowledge.py --no-dense

api:
	$(PY) -m uvicorn app.main:app --reload --port 8000

ui:
	$(PY) -m streamlit run ui/streamlit_app.py

test:
	$(PY) -m pytest -q
