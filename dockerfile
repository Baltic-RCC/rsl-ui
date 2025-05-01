# Use a JAVA base image from Eclipse Temurin with full registry path
#FROM docker.io/eclipse-temurin:17-jdk-jammy AS base
FROM docker.io/eclipse-temurin:21-jre-noble AS base


# Set working directory
WORKDIR /app

# Install Python and necessary packages in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

# Copy requirements file
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

# Copy assets and app code
COPY assets /app/assets
COPY web-app.py /app/web-app.py
COPY validation_api.py /app/validation_api.py

# Set ownership of /app to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Set environment variables
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Expose the Dash app port
EXPOSE 8050

# Run the app
CMD ["python3", "web-app.py"]