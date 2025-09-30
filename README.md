<div align="center">

<h1>Marker PDF | Worker</h1>

This repository contains the [Marker PDF](https://github.com/VikParuchuri/marker) Worker for RunPod. The Marker PDF Worker is designed to convert PDF files to Markdown, with support for tables, images, equations, and more. It's part of the RunPod Workers collection aimed at providing diverse functionality for endpoint processing.

</div>

## Model Inputs

| Input                               | Type  | Description                                                                                                                                              |
|-------------------------------------|-------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `pdf`                               | Path  | PDF file to convert                                                                                                                                      |
| `pdf_base64`                        | str   | Base64-encoded PDF file                                                                                                                                  |
| `output_format`                     | str   | Choose the format for the output. Choices: "markdown", "json", "html". Default: "markdown"                                                               |
| `paginate_output`                   | bool  | Paginates the output, using \n\n{PAGE_NUMBER} followed by separators. Default: False                                                                     |
| `use_llm`                           | bool  | Uses an LLM to improve accuracy. Default: False                                                                                                          |
| `disable_image_extraction`          | bool  | Don't extract images from the PDF. Default: False                                                                                                        |
| `page_range`                        | str   | Specify which pages to process. Accepts comma-separated page numbers and ranges. Example: "0,5-10,20"                                                   |
| `force_ocr`                         | bool  | Force OCR processing on the entire document, even for pages that might contain extractable text. Default: False                                          |
| `strip_existing_ocr`                | bool  | Remove all existing OCR text in the document and re-OCR with surya. Default: False                                                                       |
| `languages`                         | str   | Optionally specify which languages to use for OCR processing. Accepts a comma-separated list. Example: "en,fr,de"                                        |
| `model`                             | str   | Choose a model size. Choices: "default", "table". Default: "default"                                                                                    |

## Test Inputs

The following inputs can be used for testing the model:

```json
{
    "input": {
        "pdf": "https://arxiv.org/pdf/1804.07821.pdf"
    }
}
```

## Sample output
```json
{
    "markdown": "# Multi-column CNN for Single Image\n\n**Abstract**—In this paper we propose a multi-column CNN-based architecture...",
    "images": [
        {
            "filename": "image_0.png",
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

[![Runpod](https://api.runpod.io/badge/hudahoeda/runpod-marker-pdf)](https://console.runpod.io/hub/hudahoeda/runpod-marker-pdf)