FROM python:3.12-slim
WORKDIR /app
COPY app.py evaluate.py evaluate_model.py generate.py query.py date_context.py test_query.py test_evaluate_model.py test_date_context.py exercises.sql examples.json challenge_cases.json ./
CMD ["python", "app.py"]
