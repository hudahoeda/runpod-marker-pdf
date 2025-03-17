INPUT_VALIDATIONS = {
    'pdf': {
        'type': str,
        'required': False,
        'default': None
    },
    'pdf_base64': {
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