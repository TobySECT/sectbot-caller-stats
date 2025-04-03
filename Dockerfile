FROM python:3.9-slim

# Install dependencies and Chromium along with its driver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables so that Selenium can find the Chromium binary
ENV CHROME_BIN=/usr/bin/chromium-browser
ENV PATH="/usr/bin:${PATH}"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of your app code
COPY . /app
WORKDIR /app

EXPOSE 8501

# Run the Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
