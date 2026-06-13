from fastapi import HTTPException, status
from typing import Optional, Any

class WoodfulException(Exception):
    def __init__(self, message: str, status_code: int = 400, detail: Optional[Any] = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {"error": message}

class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Not enough permissions"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class ConflictError(HTTPException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class ValidationError(HTTPException):
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

class InvalidMaterialError(ValidationError):
    def __init__(self, material: str):
        super().__init__(detail=f"Invalid material type: {material}")

class InvalidThicknessError(ValidationError):
    def __init__(self, material: str, thickness: float):
        super().__init__(detail=f"Invalid thickness {thickness}mm for {material}")

class LowStockError(WoodfulException):
    def __init__(self, material: str, current: int, minimum: int):
        message = f"{material} stock ({current}) below minimum ({minimum})"
        super().__init__(message, status_code=400)

class InsufficientPermissionError(ForbiddenError):
    def __init__(self, action: str = "perform this action"):
        super().__init__(detail=f"You do not have permission to {action}")