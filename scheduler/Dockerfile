FROM python:3.10-slim

WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY TelegramBot/ TelegramBot/
COPY scheduler/ scheduler/

# Setup cron
COPY scheduler/crontab /etc/cron.d/notifications
RUN chmod 0644 /etc/cron.d/notifications && crontab /etc/cron.d/notifications

# Create log file
RUN touch /var/log/cron.log

# Run cron in foreground
CMD ["cron", "-f"]
