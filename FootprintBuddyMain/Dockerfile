FROM python:3.11-slim

# Workdir
WORKDIR /app

# Speed up Python and cleaner logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Streamlit config
ENV PORT=8501
EXPOSE 8501

# Run the app
CMD streamlit run main.py --server.address 0.0.0.0 --server.port ${PORT:-8501}