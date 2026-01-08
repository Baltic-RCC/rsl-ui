# Stage 1: Builder
FROM docker.io/eclipse-temurin:21-jre-noble AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final
FROM docker.io/eclipse-temurin:21-jre-noble

WORKDIR /app

# Install runtime dependencies (only python3, minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with fixed UID/GID to match K8s securityContext
RUN groupadd -g 3000 appgroup && \
    useradd -u 1001 -g appgroup -m -d /home/appuser appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY assets /app/assets
COPY web_app.py /app/web_app.py
COPY validation_api.py /app/validation_api.py

# Create workspace directory and set ownership
RUN mkdir -p /app/suv/workspace && \
    chown -R appuser:appgroup /app

# Switch user
USER 1001

# Environment variables
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8050

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8050/health || exit 1

# Run with Gunicorn from venv
CMD ["gunicorn", "--workers=2", "--threads=4", "--timeout=1200", "--bind=0.0.0.0:8050", "web_app:server"]
