# Dockerfile

# 1. Use an official Python runtime as a parent image
FROM python:3.10-slim

# 2. Set the working directory in the container
WORKDIR /app

# 3. Copy the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip -r requirements.txt

# 4. Copy the rest of the application code
COPY main.py ./

# 5. Expose the port the app runs on
EXPOSE 8000

# 6. Define the command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]