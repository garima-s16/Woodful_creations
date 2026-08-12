from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Location(BaseModel):
    """A flexible, arbitrary-depth location tree (Warehouse -> Area ->
    Rack -> Bin, or as few/many levels as a business actually uses) -
    self-referential rather than four rigid fixed tables, since not
    every material needs bin-level precision and users must be able to
    define their own structure without a schema change.
    location_type is a free-text hint for display/grouping ("Warehouse",
    "Rack", "Chemical Area"), not an enforced enum - matching the
    product principle that nothing important is hard-coded."""
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("parent_id", "name", name="uq_location_name_per_parent"),)

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(150), nullable=False, index=True)
    location_type = Column(String(50), nullable=True)  # "Warehouse", "Area", "Rack", "Bin", or user-defined
    parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    parent = relationship("Location", remote_side="Location.id", backref="children")

    @property
    def full_path(self):
        """"Vijay Nagar Warehouse > Rack A2 > Bin H1" - built by walking
        up the parent chain, so the UI can show exactly where something
        is without a separate denormalized path column to keep in sync."""
        parts = [self.name]
        node = self.parent
        seen_ids = {self.id}  # defensive - a corrupted parent cycle must not infinite-loop
        while node and node.id not in seen_ids:
            parts.append(node.name)
            seen_ids.add(node.id)
            node = node.parent
        return " > ".join(reversed(parts))
