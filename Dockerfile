FROM python:3.12-slim
WORKDIR /app
COPY app.py exercises.sql ./
CMD ["python", "app.py"]
