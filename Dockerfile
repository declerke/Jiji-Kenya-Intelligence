FROM apache/airflow:3.0.0

USER root

# Pre-create staging and data directories with correct permissions
RUN mkdir -p /opt/airflow/staging /data \
    && chown -R airflow:root /opt/airflow/staging /data \
    && chmod -R 775 /opt/airflow/staging /data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        wget \
        gnupg \
        libglib2.0-0 \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python dependencies into the Airflow virtualenv
# Note: Airflow 3.0 uses an internal venv; pip install (no --user) targets the venv
RUN pip install --no-cache-dir \
    playwright==1.44.0 \
    beautifulsoup4==4.12.3 \
    "dbt-duckdb==1.8.1" \
    "duckdb==1.1.3" \
    pandas==2.2.2 \
    lxml==5.2.2 \
    requests==2.32.3 \
    pytest==9.0.3 \
    pytest-asyncio>=0.24.0

# Install Playwright Chromium browser (browser binary only, no system deps needed
# because we installed all apt system deps as root above)
RUN python -m playwright install chromium

# Copy project files into the Airflow home
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root scraper/ /opt/airflow/scraper/
COPY --chown=airflow:root dbt/ /opt/airflow/dbt/
