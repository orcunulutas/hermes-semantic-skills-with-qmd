from typing import Dict, Any, Optional

class QMDError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

def format_error(code: str, message: str) -> str:
    """Format an error exactly as required by the architecture."""
    import json
    return json.dumps({
        "success": False,
        "code": code,
        "message": message
    })
