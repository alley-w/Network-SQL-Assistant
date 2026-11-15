FROM python:3.12-slim
WORKDIR /app
COPY app.py evaluate.py evaluate_model.py generate.py query.py test_query.py test_evaluate_model.py exercises.sql examples.json ./
CMD ["python", "app.py"]
