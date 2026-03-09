FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Set environment variables
ENV DATABASE_URL=sqlite+aiosqlite:///./data/relationshipos.db
ENV JWT_SECRET_KEY=production-secret-change-me-in-env
ENV CORS_ORIGINS=*
ENV APP_NAME=RelationshipOS
ENV APP_VERSION=1.0.0

# Expose port
EXPOSE 8000

# Run seed data then start the server
CMD python seed_data.py && uvicorn app.main:app --host 0.0.0.0 --port 8000
