FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py reports.py bot.py ./

# SQLite database and .env are mounted at runtime
CMD ["python", "-u", "bot.py"]
