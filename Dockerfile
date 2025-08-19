# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (like the GLPK solver)
# This command updates the package list and installs the glpk-utils package.
RUN apt-get update && apt-get install -y glpk-utils

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed Python packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code (app.py, pages/, etc.) into the container
COPY . .

# Make port 8080 available to the world outside this container
# This is the port Cloud Run will use.
EXPOSE 8080

# Define the command to run the app when the container starts.
# This "shell" form correctly uses the $PORT variable provided by Cloud Run.
CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
