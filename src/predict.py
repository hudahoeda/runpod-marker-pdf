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
from marker.services.gemini import GoogleGeminiService


class Predictor:
    """ A Predictor class for the Marker PDF converter """

    def __init__(self):
        self.model_artifacts = {}

    def setup(self):
        """Load the model into memory to make running multiple predictions efficient"""
        # Create model artifacts once
        self.model_artifacts = create_model_dict()
        
    def _optimize_image(self, image_input, filename_hint="image.jpg", max_size=(1024, 1024), quality=85, max_file_size=1*1024*1024):
        """
        Optimize an image to reduce its file size before encoding to base64.
        
        Args:
            image_input: Path to the image file or a PIL.Image.Image object
            filename_hint: A filename to use if the input is an Image object or if path processing fails
            max_size: Maximum dimensions (width, height) to resize to
            quality: JPEG quality (1-100)
            max_file_size: Maximum file size in bytes
            
        Returns:
            tuple: (Optimized image data as bytes, filename as str) or (None, filename_hint) on failure
        """
        img = None
        actual_filename = filename_hint

        try:
            if isinstance(image_input, Image.Image):
                img = image_input
                # actual_filename remains filename_hint as we don't have an original path
            elif isinstance(image_input, (str, Path)):
                image_path_obj = Path(image_input)
                actual_filename = image_path_obj.name
                if not image_path_obj.exists():
                    print(f"Error: Image path {image_path_obj} does not exist.", file=sys.stderr)
                    return None, actual_filename
                img = Image.open(image_path_obj)
            else:
                print(f"Error: Unsupported image input type {type(image_input)}.", file=sys.stderr)
                return None, actual_filename

            if img is None: # Should be caught by previous checks, but as a safeguard
                print(f"Error: Image could not be processed from input.", file=sys.stderr)
                return None, actual_filename

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
            
            return data, actual_filename
        except Exception as e:
            error_source_info = actual_filename if isinstance(image_input, (str, Path)) else f"PIL.Image object ({filename_hint})"
            print(f"Error optimizing image {error_source_info}: {str(e)}", file=sys.stderr)
            # Fallback for path input, try to return original if it exists
            if isinstance(image_input, (str, Path)) and Path(image_input).exists():
                try:
                    with open(image_input, "rb") as f:
                        return f.read(), actual_filename
                except Exception as e_read:
                    print(f"Error reading original image {actual_filename} during fallback: {str(e_read)}", file=sys.stderr)
            return None, actual_filename
        
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
        # Instantiate LLM service if use_llm is true
        llm_service_instance = None
        if use_llm:
            try:
                # Assuming GoogleGeminiService reads GOOGLE_API_KEY from env
                llm_service_instance = GoogleGeminiService()
            except ImportError:
                print("Warning: GoogleGeminiService could not be imported. LLM features might be unavailable.", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Could not instantiate GoogleGeminiService: {e}. LLM features might be unavailable.", file=sys.stderr)

        # Prepare the configuration dictionary for the converter constructor
        converter_config = {
            "disable_image_extraction": disable_image_extraction,
            "force_ocr": force_ocr,
            "strip_existing_ocr": strip_existing_ocr,
        }
        
        if page_range:
            converter_config["page_range"] = page_range # marker might expect a list/parsed format
            
        if languages:
            converter_config["languages"] = languages.split(",")
            
        # Determine converter class and update config if model is "table"
        if model == "table":
            converter_class = TableConverter
            converter_config["force_layout_block"] = "Table"
        else:
            converter_class = PdfConverter
        
        # Set device type
        device = "cuda" if rp_cuda.is_available() else "cpu"
        
        # Create the converter instance
        converter = converter_class(
            artifact_dict=self.model_artifacts,
            llm_service=llm_service_instance,
            config=converter_config # Pass the config dictionary here
        )
        
        # Convert the PDF - __call__ method should only take the path
        rendered = converter(str(pdf_path))
        
        # Process results based on output format
        results = {}
        
        # Store the original output
        if output_format == "markdown":
            results["markdown"] = rendered.markdown
            results["metadata"] = rendered.metadata
            
            # Process images if they were extracted
            if not disable_image_extraction and hasattr(rendered, 'images') and rendered.images:
                processed_images_list = [] # Use a new name for clarity
                
                source_image_references = []
                if isinstance(rendered.images, dict):
                    source_image_references = list(rendered.images.values())
                elif isinstance(rendered.images, list):
                    source_image_references = rendered.images
                else:
                    print(f"Warning: rendered.images is of unexpected type: {type(rendered.images)}. Skipping image processing.", file=sys.stderr)

                if source_image_references:
                    max_images_to_process = min(10, len(source_image_references))
                    
                    for i, img_ref in enumerate(source_image_references[:max_images_to_process]):
                        optimized_img_data = None
                        img_filename = f"image_{i}.jpg" # Default/fallback filename

                        if isinstance(img_ref, (str, Path)):
                            # It's a path-like object
                            image_path_obj = Path(img_ref)
                            if image_path_obj.exists():
                                optimized_img_data, img_filename = self._optimize_image(image_path_obj)
                            else:
                                print(f"Warning: Image path does not exist {image_path_obj}", file=sys.stderr)
                        elif isinstance(img_ref, Image.Image): # It's a PIL Image object
                            optimized_img_data, img_filename = self._optimize_image(img_ref, filename_hint=f"embedded_image_{i}.jpg")
                        else:
                            print(f"Warning: img_ref is of unsupported type: {type(img_ref)}. Skipping image {i}.", file=sys.stderr)
                            continue # Skip to next image processing

                        if optimized_img_data:
                            try:
                                # Optimize and encode the image
                                img_data = base64.b64encode(optimized_img_data).decode("utf-8")
                                processed_images_list.append({
                                    "filename": img_filename, # Use filename from _optimize_image
                                    "data": img_data
                                })
                            except Exception as e:
                                print(f"Error encoding image {i} ({img_filename}): {str(e)}", file=sys.stderr)
                        # else: # Optional: log if optimization returned None
                        #     print(f"Warning: Optimization failed for image {i} ({img_filename if img_filename else img_ref})", file=sys.stderr)
                
                    if processed_images_list:
                        results["images"] = processed_images_list

                    if len(source_image_references) > max_images_to_process and processed_images_list:
                        results["images_truncated"] = True
                        results["total_images"] = len(source_image_references)
                    elif len(source_image_references) > 0 and not processed_images_list : # Had images, but none were processed
                        results["total_images"] = len(source_image_references)

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
                processed_images_list = [] # Use a new name for clarity
                
                source_image_references = []
                if isinstance(rendered.images, dict):
                    source_image_references = list(rendered.images.values())
                elif isinstance(rendered.images, list):
                    source_image_references = rendered.images
                else:
                    print(f"Warning: rendered.images is of unexpected type: {type(rendered.images)}. Skipping image processing.", file=sys.stderr)

                if source_image_references:
                    max_images_to_process = min(10, len(source_image_references))
                    
                    for i, img_ref in enumerate(source_image_references[:max_images_to_process]):
                        optimized_img_data = None
                        img_filename = f"image_{i}.jpg" # Default/fallback filename

                        if isinstance(img_ref, (str, Path)):
                            # It's a path-like object
                            image_path_obj = Path(img_ref)
                            if image_path_obj.exists():
                                optimized_img_data, img_filename = self._optimize_image(image_path_obj)
                            else:
                                print(f"Warning: Image path does not exist {image_path_obj}", file=sys.stderr)
                        elif isinstance(img_ref, Image.Image): # It's a PIL Image object
                            optimized_img_data, img_filename = self._optimize_image(img_ref, filename_hint=f"embedded_image_{i}.jpg")
                        else:
                            print(f"Warning: img_ref is of unsupported type: {type(img_ref)}. Skipping image {i}.", file=sys.stderr)
                            continue # Skip to next image processing
                        
                        if optimized_img_data:
                            try:
                                # Optimize and encode the image
                                img_data = base64.b64encode(optimized_img_data).decode("utf-8")
                                processed_images_list.append({
                                    "filename": img_filename, # Use filename from _optimize_image
                                    "data": img_data
                                })
                            except Exception as e:
                                print(f"Error encoding image {i} ({img_filename}): {str(e)}", file=sys.stderr)
                        # else: # Optional: log if optimization returned None
                        #     print(f"Warning: Optimization failed for image {i} ({img_filename if img_filename else img_ref})", file=sys.stderr)

                    if processed_images_list:
                        results["images"] = processed_images_list
                        
                    if len(source_image_references) > max_images_to_process and processed_images_list:
                        results["images_truncated"] = True
                        results["total_images"] = len(source_image_references)
                    elif len(source_image_references) > 0 and not processed_images_list : # Had images, but none were processed
                        results["total_images"] = len(source_image_references)
        
        # Additional info
        results["device"] = device
        results["model"] = model # 'model' is the original input parameter
            
        return results 