FROM python:3.12-slim
WORKDIR /app
COPY app.py evaluate.py generate.py query.py test_query.py exercises.sql examples.json ./
CMD ["python", "app.py"]
