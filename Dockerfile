# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies from packages.txt
# This is necessary for libraries like GLPK
COPY packages.txt .
RUN apt-get update && apt-get install -y --no-install-recommends $(cat packages.txt)

# Copy the Python requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application's code into the container
COPY . .

# Expose the port that Cloud Run will use
EXPOSE 8080

# Define the command to run your app
# This tells Streamlit to run on the port provided by the PORT environment variable
# Using the shell form (without brackets) ensures the $PORT variable is correctly interpreted.
# --server.headless=true is a best practice for running in a container.
CMD streamlit run 👋_Introduction.py --server.headless true --server.port $PORT --server.enableCORS false --server.enableXsrfProtection false
