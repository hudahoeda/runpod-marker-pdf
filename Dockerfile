FROM runpod/base:0.6.3-cuda11.8.0

# Ensure python 3.11 is the default interpreter
RUN ln -sf $(which python3.11) /usr/local/bin/python \
    && ln -sf $(which python3.11) /usr/local/bin/python3

WORKDIR /workspace

# Install minimal system dependencies for image processing
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with uv
COPY requirements.txt /workspace/requirements.txt
RUN uv pip install --upgrade -r /workspace/requirements.txt --no-cache-dir --system

# Add worker sources
COPY handler.py predict.py /workspace/

# Warm up marker model artifacts during build
RUN python -c "import predict; predictor = predict.Predictor(); predictor.setup()"

# Start the serverless handler
CMD ["python", "-u", "/workspace/handler.py"]
