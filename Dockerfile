# Use the official Python 3.8 slim image as the base image
FROM python:3.8-slim

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code and entrypoint script into the container
COPY main.py entrypoint.sh ./

# Make the entrypoint script executable
RUN chmod +x entrypoint.sh

# Set the entrypoint for the container to be the entrypoint.sh script
ENTRYPOINT ["/entrypoint.sh"]
