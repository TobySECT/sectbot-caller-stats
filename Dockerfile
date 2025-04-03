FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium-browser
ENV PATH="/usr/bin:${PATH}"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app
WORKDIR /app

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
