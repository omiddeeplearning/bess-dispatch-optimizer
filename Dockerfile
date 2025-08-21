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
# The key change is adding --server.address=0.0.0.0
# This tells Streamlit to listen for connections from outside the container, which is required by Cloud Run.
CMD streamlit run 👋_Introduction.py --server.headless true --server.address=0.0.0.0 --server.port $PORT --server.enableCORS false --server.enableXsrfProtection false
