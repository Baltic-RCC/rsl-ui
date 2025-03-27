# Use a JDK 17 base image from Eclipse Temurin
FROM eclipse-temurin:17-jdk-jammy AS base

# Set working directory
WORKDIR /app

# Install Python and necessary packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment
RUN python3 -m venv /app/venv

# Activate virtual environment and install Python packages
ENV PATH="/app/venv/bin:$PATH"

# Install required Python packages (update as needed)
RUN pip install --upgrade pip && pip install \
    dash \
    flask \
    werkzeug

# Copy app code
COPY web-app.py /app/web-app.py
COPY validation_api.py /app/validation_api.py

# Copy your SVT tool folders
COPY lib /app/lib
COPY workspace /app/workspace
COPY etc /app/etc

# Set JAVA_HOME (usually already correct, but just in case)
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Expose the Dash/Flask app port
EXPOSE 8050

# Run the app
CMD ["python3", "web-app.py"]
