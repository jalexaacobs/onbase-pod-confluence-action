# running with python
FROM python:3.9

# Copy resources to the filesystem path `/` of the container
COPY UpdateConfluence.py /UpdateConfluence.py
COPY requirements.txt /requirements.txt

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3-pip
RUN pip install -r requirements.txt

# just running the script
ENTRYPOINT [ "python", "/UpdateConfluence.py"]