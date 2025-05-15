"""
This file contains the Predictor class, which is used to convert PDFs to Markdown
using the marker-pdf library.
"""

import base64
import json
import os
import sys
from pathlib import Path
import tempfile
from io import BytesIO
from PIL import Image

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
        
    def _optimize_image(self, image_path, max_size=(1024, 1024), quality=85, max_file_size=1*1024*1024):
        """
        Optimize an image to reduce its file size before encoding to base64.
        
        Args:
            image_path: Path to the image file
            max_size: Maximum dimensions (width, height) to resize to
            quality: JPEG quality (1-100)
            max_file_size: Maximum file size in bytes
            
        Returns:
            bytes: Optimized image data
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if RGBA
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Resize if necessary
                if img.width > max_size[0] or img.height > max_size[1]:
                    img.thumbnail(max_size, Image.LANCZOS)
                
                # Save to memory buffer
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=quality, optimize=True)
                
                # If still too large, reduce quality until under max_file_size
                data = buffer.getvalue()
                current_quality = quality
                
                while len(data) > max_file_size and current_quality > 10:
                    current_quality -= 10
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=current_quality, optimize=True)
                    data = buffer.getvalue()
                
                return data
        except Exception as e:
            print(f"Error optimizing image {image_path}: {str(e)}", file=sys.stderr)
            # Return original file if optimization fails
            with open(image_path, "rb") as f:
                return f.read()
        
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
                # Limit to maximum 10 images to prevent response size issues
                max_images = min(10, len(rendered.images))
                
                for i, img in enumerate(rendered.images[:max_images]):
                    # Get image path
                    image_path = Path(img)
                    if image_path.exists():
                        try:
                            # Optimize and encode the image
                            optimized_img_data = self._optimize_image(image_path)
                            img_data = base64.b64encode(optimized_img_data).decode("utf-8")
                            images.append({
                                "filename": image_path.name,
                                "data": img_data
                            })
                        except Exception as e:
                            print(f"Error processing image {i}: {str(e)}", file=sys.stderr)
                
                results["images"] = images
                if len(rendered.images) > max_images:
                    results["images_truncated"] = True
                    results["total_images"] = len(rendered.images)
                
        elif output_format == "json":
            # For JSON output, we need to convert the pydantic model to dict
            json_data = rendered.json()
            parsed_data = json.loads(json_data)
            
            # For JSON output, don't include the images to keep the response size manageable
            if 'images' in parsed_data:
                del parsed_data['images']
            
            results = parsed_data
            
        elif output_format == "html":
            results["html"] = rendered.html
            results["metadata"] = rendered.metadata
            
            # Process images if they were extracted
            if not disable_image_extraction and hasattr(rendered, 'images') and rendered.images:
                images = []
                # Limit to maximum 10 images to prevent response size issues
                max_images = min(10, len(rendered.images))
                
                for i, img in enumerate(rendered.images[:max_images]):
                    # Get image path
                    image_path = Path(img)
                    if image_path.exists():
                        try:
                            # Optimize and encode the image
                            optimized_img_data = self._optimize_image(image_path)
                            img_data = base64.b64encode(optimized_img_data).decode("utf-8")
                            images.append({
                                "filename": image_path.name,
                                "data": img_data
                            })
                        except Exception as e:
                            print(f"Error processing image {i}: {str(e)}", file=sys.stderr)
                
                results["images"] = images
                if len(rendered.images) > max_images:
                    results["images_truncated"] = True
                    results["total_images"] = len(rendered.images)
        
        # Additional info
        results["device"] = device
        results["model"] = model
            
        return results 