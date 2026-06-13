import pytest
from app.core.constants import MATERIAL_TYPES

def test_material_validation():
    for material, thicknesses in MATERIAL_TYPES.items():
        assert len(thicknesses) > 0

def test_invalid_material():
    pass

def test_invalid_thickness():
    pass