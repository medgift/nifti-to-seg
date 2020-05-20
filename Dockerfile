FROM python:3.6

MAINTAINER Roger Schaer <roger.schaer@hevs.ch>

# Define working directory
WORKDIR /usr/src/app

# Copy & install requirements
COPY ./requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

# Copy source code
COPY . .

# Define entrypoint
ENTRYPOINT ["python", "/usr/src/app/nifti_to_seg.py"]

# Default command - show help
CMD ["--help"]