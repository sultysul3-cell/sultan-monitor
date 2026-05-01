FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY crash_monitor.py .

CMD ["python", "crash_monitor.py"]
