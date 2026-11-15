FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY network_sql/ ./network_sql/
COPY tests/ ./tests/
COPY benchmarks/ ./benchmarks/
COPY app.py ui.py generate.py evaluate.py evaluate_model.py exercises.sql ./
CMD ["python", "app.py"]
