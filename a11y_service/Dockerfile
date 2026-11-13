FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir -e .
COPY knowledge ./knowledge
COPY scripts ./scripts
COPY ui ./ui
EXPOSE 8000 8501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
