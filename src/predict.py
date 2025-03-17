"""
This file contains the Predictor class, which is used to convert PDFs to Markdown
using the marker-pdf library.
"""

import base64
import json
import os
from pathlib import Path
import tempfile

from marker.converters.pdf import PdfConverter
from marker.converters.table import TableConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from runpod.serverless.utils import rp_cuda


class Predictor:
    """ A Predictor class for the Marker PDF converter """

    def __init__(self):
        self.model_artifacts = {}

    def setup(self):
        """Load the model into memory to make running multiple predictions efficient"""
        # Create model artifacts once
        self.model_artifacts = create_model_dict()
        
    def predict(
        self,
        pdf_path,
        output_format="markdown",
        paginate_output=False,
        use_llm=False,
        disable_image_extraction=False,
        page_range=None,
        force_ocr=False,
        strip_existing_ocr=False,
        languages=None,
        model="default"
    ):
        """
        Run a single prediction on the model
        """
        # Set up configuration dictionary
        config = {
            "output_format": output_format,
            "paginate_output": paginate_output,
            "use_llm": use_llm,
            "disable_image_extraction": disable_image_extraction,
            "force_ocr": force_ocr,
            "strip_existing_ocr": strip_existing_ocr,
        }
        
        # Add optional configurations
        if page_range:
            config["page_range"] = page_range
            
        if languages:
            config["languages"] = languages.split(",")
            
        # Determine which converter to use
        if model == "table":
            converter_class = TableConverter
            config["force_layout_block"] = "Table"
        else:
            converter_class = PdfConverter
        
        # Set device type
        device = "cuda" if rp_cuda.is_available() else "cpu"
        
        # Create the converter instance
        converter = converter_class(
            artifact_dict=self.model_artifacts,
            device=device,
            **config
        )
        
        # Convert the PDF
        rendered = converter(str(pdf_path))
        
        # Process results based on output format
        results = {}
        
        # Store the original output
        if output_format == "markdown":
            results["markdown"] = rendered.markdown
            results["metadata"] = rendered.metadata
            
            # Process images if they were extracted
            if not disable_image_extraction and hasattr(rendered, 'images') and rendered.images:
                images = []
                for i, img in enumerate(rendered.images):
                    # Get image path
                    image_path = Path(img)
                    if image_path.exists():
                        # Read image and convert to base64
                        with open(image_path, "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode("utf-8")
                            images.append({
                                "filename": image_path.name,
                                "data": img_data
                            })
                results["images"] = images
                
        elif output_format == "json":
            # For JSON output, we need to convert the pydantic model to dict
            json_data = rendered.json()
            results = json.loads(json_data)
            
        elif output_format == "html":
            results["html"] = rendered.html
            results["metadata"] = rendered.metadata
            
            # Process images if they were extracted
            if not disable_image_extraction and hasattr(rendered, 'images') and rendered.images:
                images = []
                for i, img in enumerate(rendered.images):
                    # Get image path
                    image_path = Path(img)
                    if image_path.exists():
                        # Read image and convert to base64
                        with open(image_path, "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode("utf-8")
                            images.append({
                                "filename": image_path.name,
                                "data": img_data
                            })
                results["images"] = images
        
        # Additional info
        results["device"] = device
        results["model"] = model
            
        return results 