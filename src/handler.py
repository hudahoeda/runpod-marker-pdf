""" 
Handler for Marker PDF worker.

This module handles the requests for the marker-pdf RunPod worker.
"""
import base64
import json
import sys
import tempfile
import time
from pathlib import Path

import filetype
import runpod
from runpod.serverless.utils import download_files_from_urls, rp_cleanup, rp_debugger
from runpod.serverless.utils.rp_validator import validate

# Import predict module from current directory
from predict import Predictor

# Input validation schema
INPUT_VALIDATIONS = {
    'pdf': {
        'type': str,
        'required': False,
        'default': None
    },
    'file': {
        'type': str,
        'required': False,
        'default': None
    },
    'pdf_base64': {
        'type': str,
        'required': False,
        'default': None
    },
    'file_base64': {
        'type': str,
        'required': False,
        'default': None
    },
    'filename': {
        'type': str,
        'required': False,
        'default': None
    },
    'output_format': {
        'type': str,
        'required': False,
        'default': 'markdown',
        'enum': ['markdown', 'json', 'html']
    },
    'paginate_output': {
        'type': bool,
        'required': False,
        'default': False
    },
    'use_llm': {
        'type': bool,
        'required': False,
        'default': False
    },
    'disable_image_extraction': {
        'type': bool,
        'required': False,
        'default': False
    },
    'page_range': {
        'type': str,
        'required': False,
        'default': None
    },
    'force_ocr': {
        'type': bool,
        'required': False,
        'default': False
    },
    'strip_existing_ocr': {
        'type': bool,
        'required': False,
        'default': False
    },
    'languages': {
        'type': str,
        'required': False,
        'default': None
    },
    'model': {
        'type': str,
        'required': False,
        'default': 'default',
        'enum': ['default', 'table']
    }
}

# Load the model into memory to make running multiple predictions efficient
MODEL = Predictor()
MODEL.setup()


def _extract_base64_payload(data: str) -> str:
    """Remove data URL prefixes from base64 strings if present."""
    if data.startswith("data:"):
        try:
            return data.split(",", 1)[1]
        except IndexError:
            return data
    return data


def base64_to_tempfile(base64_file: str, filename_hint: str | None = None) -> str:
    '''
    Convert base64 file to tempfile.

    Parameters:
    base64_file (str): Base64 file

    Returns:
    str: Path to tempfile
    '''
    payload = _extract_base64_payload(base64_file)

    try:
        file_bytes = base64.b64decode(payload, validate=False)
    except (base64.binascii.Error, ValueError) as decode_error:
        raise ValueError("Invalid base64 file payload") from decode_error

    suffix = None

    if filename_hint:
        suffix = Path(filename_hint).suffix

    if not suffix:
        guessed = filetype.guess(file_bytes)
        if guessed:
            suffix = f".{guessed.extension}"

    if not suffix:
        suffix = ".pdf"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_file.write(file_bytes)

    return temp_file.name


def truncate_long_string(s, max_length=1000000):
    """Truncate string if it's too long to prevent large responses."""
    if isinstance(s, str) and len(s) > max_length:
        return s[:max_length] + "... [truncated due to length]"
    return s


def sanitize_response(data, max_image_count=5):
    """
    Recursively sanitize the response to ensure it can be properly serialized.
    - Truncate long strings
    - Limit number of images
    - Convert non-serializable objects to strings
    """
    if isinstance(data, dict):
        sanitized = {}
        # Limit the number of images
        if "images" in data and isinstance(data["images"], list) and len(data["images"]) > max_image_count:
            data["images"] = data["images"][:max_image_count]
            data["images_note"] = f"Only showing {max_image_count} images out of {len(data['images'])} due to size limits"
        
        # Process each key-value pair
        for key, value in data.items():
            sanitized[key] = sanitize_response(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_response(item) for item in data]
    elif isinstance(data, str):
        return truncate_long_string(data)
    elif isinstance(data, (int, float, bool, type(None))):
        return data
    else:
        # Convert any other types to string to ensure serializability
        return str(data)


def handler(job):
    """
    Handler function that will be used to process jobs.
    """
    try:
        job_input = job['input']
        start_time = time.time()

        with rp_debugger.LineTimer('validation_step'):
            input_validation = validate(job_input, INPUT_VALIDATIONS)

            if 'errors' in input_validation:
                return {"error": input_validation['errors']}
            job_input = input_validation['validated_input']

        file_url = next((job_input[key] for key in ['file', 'pdf'] if job_input.get(key)), None)
        file_base64 = next((job_input[key] for key in ['file_base64', 'pdf_base64'] if job_input.get(key)), None)

        if not file_url and not file_base64:
            return {'error': 'Must provide either file/pdf or file_base64/pdf_base64'}

        if file_url and file_base64:
            return {'error': 'Must provide either file/pdf or file_base64/pdf_base64, not both'}

        filename_hint = job_input.get('filename')

        if file_url:
            with rp_debugger.LineTimer('download_step'):
                file_input = download_files_from_urls(job['id'], [file_url])[0]
        else:
            file_input = base64_to_tempfile(file_base64, filename_hint=filename_hint)

        with rp_debugger.LineTimer('prediction_step'):
            results = MODEL.predict(
                file_path=file_input,
                output_format=job_input["output_format"],
                paginate_output=job_input["paginate_output"],
                use_llm=job_input["use_llm"],
                disable_image_extraction=job_input["disable_image_extraction"],
                page_range=job_input["page_range"],
                force_ocr=job_input["force_ocr"],
                strip_existing_ocr=job_input["strip_existing_ocr"],
                languages=job_input["languages"],
                model=job_input["model"]
            )

        with rp_debugger.LineTimer('cleanup_step'):
            rp_cleanup.clean(['input_objects'])

        # Add processing time info
        processing_time = time.time() - start_time
        results["processing_time"] = processing_time
        
        # Sanitize the results to ensure they can be serialized properly
        sanitized_results = sanitize_response(results)
        
        # Test if results can be properly serialized
        try:
            json.dumps(sanitized_results)
        except (TypeError, OverflowError) as e:
            print(f"Warning: Serialization error detected: {str(e)}", file=sys.stderr)
            # If serialization fails, return a simplified error message
            return {
                "error": "Results could not be serialized properly",
                "message": "The PDF processing completed but the results were too complex to return via API. Try using a simpler output format or processing fewer pages."
            }
        
        return sanitized_results
        
    except Exception as e:
        import traceback
        error_message = str(e)
        stack_trace = traceback.format_exc()
        print(f"Error in handler: {error_message}\n{stack_trace}", file=sys.stderr)
        return {"error": error_message, "details": stack_trace}


runpod.serverless.start({"handler": handler})
