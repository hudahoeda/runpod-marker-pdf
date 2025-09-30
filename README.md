# Marker Document Converter Worker

This repository packages a RunPod Serverless worker that converts documents to
Markdown, JSON, or HTML using the
[Marker](https://github.com/VikParuchuri/marker) library. It supports PDFs,
Office documents, images, HTML, and more via Marker’s `full` feature set.

[![RunPod](https://api.runpod.io/badge/hudahoeda/runpod-marker-pdf)](https://console.runpod.io/hub/hudahoeda/runpod-marker-pdf)

---

## Getting Started

1. **Use this template** – clone or fork the repository.
2. **Install dependencies** – `pip install -r requirements.txt` (Python 3.11+).
3. **Test locally** – `python handler.py --test` runs the worker with
   `test_input.json`.
4. **Deploy** – connect the repo to RunPod Serverless or build/push the Docker
   image manually.

## Repository Layout

```
runpod-marker-pdf/
├── Dockerfile          # Container definition based on runpod/base
├── handler.py          # RunPod handler entrypoint
├── predict.py          # Marker conversion helper class
├── requirements.txt    # Python dependencies (installed with uv)
├── test_input.json     # Sample event payload for local testing
├── LICENSE
└── .runpod/
    ├── hub.json        # Hub listing metadata
    └── tests.json      # Automated Hub test configuration
```

## Worker Inputs

The handler accepts the following keys under the `input` payload:

| Key                       | Type  | Description |
|---------------------------|-------|-------------|
| `file`                    | str   | Direct URL to the document. |
| `file_base64`             | str   | Base64-encoded document payload. |
| `filename`                | str   | Optional filename hint (helps detect base64 types). |
| `output_format`           | str   | `markdown`, `json`, or `html`. Default `markdown`. |
| `paginate_output`         | bool  | Insert page break markers. |
| `use_llm`                 | bool  | Enable LLM-assisted formatting (requires LLM credentials). |
| `disable_image_extraction`| bool  | Skip image extraction to reduce payload size. |
| `page_range`              | str   | Page list/ranges (e.g. `0,5-10`). |
| `force_ocr`               | bool  | Force OCR on every page. |
| `strip_existing_ocr`      | bool  | Remove embedded OCR text before processing. |
| `languages`               | str   | Comma-separated OCR languages. |
| `model`                   | str   | Converter pipeline (`default` or `table`). |

Provide either `file` or `file_base64` (not both).

## Running Locally

```
pip install -r requirements.txt
python handler.py --test
```

The `--test` flag loads `test_input.json`, runs the handler once, and prints the
result. Remove the flag to start the worker as RunPod would in production.

## Sample Output

```json
{
  "markdown": "# Multi-column CNN for Single Image\n\n**Abstract**—In this paper we propose a multi-column CNN-based architecture...",
  "images": [
    {
      "filename": "image_0.jpg",
      "data": "base64_encoded_image_data"
    }
  ],
  "metadata": {
    "title": "Multi-column CNN for Single Image",
    "pages": 8,
    "detected_language": "en"
  }
}
```

## Deploying to RunPod

You can deploy via:

1. **GitHub integration (recommended)** – connect the repository in the RunPod
   console; builds trigger on pushes.
2. **Manual Docker build** – `docker build -t <image>` then push to your
   registry and point a RunPod template at the image.

See the [RunPod Serverless documentation](https://docs.runpod.io/serverless/overview)
for detailed deployment steps.
