from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class MaterialAttributeDefinition(BaseModel):
    """Defines what specification fields make sense for a subcategory -
    e.g. Plywood needs Brand/Grade/Thickness/Sheet Length/Sheet Width;
    LED Strip needs Voltage/Wattage/Colour Temperature. Each subcategory
    defines its own set rather than every material sharing one rigid
    universal column list."""
    __tablename__ = "material_attribute_definitions"
    __table_args__ = (UniqueConstraint("subcategory_id", "name", name="uq_attribute_per_subcategory"),)

    subcategory_id = Column(Integer, ForeignKey("material_subcategories.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # "Thickness", "Voltage", "Colour Temperature"
    data_type = Column(String(20), nullable=False, default="text")  # text / number / select
    unit_label = Column(String(20), nullable=True)  # "mm", "V", "K" - display only, not parsed
    # Comma-separated allowed values, only meaningful when data_type="select"
    # (e.g. "Matte,Glossy,Textured" for a laminate Finish attribute).
    select_options = Column(String(500), nullable=True)
    is_required = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)

    subcategory = relationship("MaterialSubcategory", back_populates="attribute_definitions")

    @property
    def select_options_list(self):
        if not self.select_options:
            return []
        return [o.strip() for o in self.select_options.split(",") if o.strip()]


class MaterialAttributeValue(BaseModel):
    """The actual value of one attribute for one material. Stored in a
    typed column matching the attribute's data_type (value_number for
    numeric attributes, value_text for text/select) rather than a single
    stringified column, so numeric attributes can actually be filtered
    and sorted with real SQL comparisons (thickness > 12), not string
    parsing - this is the "supports filtering/searching/reporting"
    requirement, not just a display convenience."""
    __tablename__ = "material_attribute_values"
    __table_args__ = (UniqueConstraint("material_id", "attribute_definition_id", name="uq_value_per_material_attribute"),)

    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    attribute_definition_id = Column(Integer, ForeignKey("material_attribute_definitions.id"), nullable=False, index=True)
    value_text = Column(String(255), nullable=True)
    value_number = Column(Numeric(14, 4), nullable=True, index=True)

    material = relationship("Material", back_populates="attribute_values")
    attribute_definition = relationship("MaterialAttributeDefinition")

    @property
    def attribute_name(self):
        return self.attribute_definition.name if self.attribute_definition else None

    @property
    def display_value(self):
        if self.value_number is not None:
            unit = self.attribute_definition.unit_label if self.attribute_definition else None
            num_str = f"{self.value_number:g}"
            return f"{num_str} {unit}".strip() if unit else num_str
        return self.value_text or ""
