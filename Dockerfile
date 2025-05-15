# Base image -> https://github.com/runpod/containers/blob/main/official-templates/base/Dockerfile
# DockerHub -> https://hub.docker.com/r/runpod/base/tags
FROM runpod/base:0.4.0-cuda11.8.0

# The base image comes with many system dependencies pre-installed to help you get started quickly.
# Please refer to the base image's Dockerfile for more information before adding additional dependencies.
# IMPORTANT: The base image overrides the default huggingface cache location.

# Set working directory
WORKDIR /

# --- System dependencies ---
COPY builder/setup.sh /setup.sh
RUN /bin/bash /setup.sh && \
    rm /setup.sh

# Python dependencies
COPY builder/requirements.txt /requirements.txt
RUN python3.11 -m pip install --upgrade pip && \
    python3.11 -m pip install --upgrade -r /requirements.txt --no-cache-dir && \
    # Make sure Pillow is installed with all needed features for image processing
    python3.11 -m pip install --upgrade Pillow --no-cache-dir && \
    rm /requirements.txt

# Add src files
ADD src .

# Ensure models used by marker.models.create_model_dict() are downloaded and cached during build.
# This is a placeholder command; you'll need to adapt it based on how marker-pdf caches models.
# If create_model_dict() downloads to a standard Hugging Face cache, and runpod/base configures it, this might be enough.
# Otherwise, you might need a dedicated script.
RUN python3.11 -c "import sys; sys.path.append('.'); from predict import Predictor; p = Predictor(); p.setup()"

# Set default command
CMD python3.11 -u /handler.py 