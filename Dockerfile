FROM python:3.12-slim
WORKDIR /app
COPY app.py evaluate.py exercises.sql examples.json ./
CMD ["python", "app.py"]
