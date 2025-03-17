"""
rp_handler.py for runpod worker

This module handles the requests for the marker-pdf RunPod worker.
"""
import base64
import os
import tempfile
import time

from rp_schema import INPUT_VALIDATIONS
from runpod.serverless.utils import download_files_from_urls, rp_cleanup, rp_debugger
from runpod.serverless.utils.rp_validator import validate
import runpod
import predict


MODEL = predict.Predictor()
MODEL.setup()


def base64_to_tempfile(base64_file: str) -> str:
    '''
    Convert base64 file to tempfile.

    Parameters:
    base64_file (str): Base64 file

    Returns:
    str: Path to tempfile
    '''
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_file.write(base64.b64decode(base64_file))

    return temp_file.name


@rp_debugger.FunctionTimer
def run_marker_pdf_job(job):
    '''
    Run the marker pdf conversion.

    Parameters:
    job (dict): Input job containing the model parameters

    Returns:
    dict: The result of the conversion
    '''
    job_input = job['input']
    start_time = time.time()

    with rp_debugger.LineTimer('validation_step'):
        input_validation = validate(job_input, INPUT_VALIDATIONS)

        if 'errors' in input_validation:
            return {"error": input_validation['errors']}
        job_input = input_validation['validated_input']

    if not job_input.get('pdf', False) and not job_input.get('pdf_base64', False):
        return {'error': 'Must provide either pdf or pdf_base64'}

    if job_input.get('pdf', False) and job_input.get('pdf_base64', False):
        return {'error': 'Must provide either pdf or pdf_base64, not both'}

    if job_input.get('pdf', False):
        with rp_debugger.LineTimer('download_step'):
            pdf_input = download_files_from_urls(job['id'], [job_input['pdf']])[0]

    if job_input.get('pdf_base64', False):
        pdf_input = base64_to_tempfile(job_input['pdf_base64'])

    with rp_debugger.LineTimer('prediction_step'):
        results = MODEL.predict(
            pdf_path=pdf_input,
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

    return results


runpod.serverless.start({"handler": run_marker_pdf_job}) 