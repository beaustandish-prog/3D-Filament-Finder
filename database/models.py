from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    inventory = relationship("Inventory", back_populates="owner")
    spool_history = relationship("SpoolHistory", back_populates="owner")

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # Link to User
    
    brand = Column(String, index=True)
    material = Column(String)
    color_name = Column(String)
    color_hex = Column(String)
    weight_initial_g = Column(Integer)
    weight_remaining_g = Column(Integer)
    diameter = Column(Float)
    temp_nozzle = Column(String)
    location = Column(String)
    date_added = Column(DateTime, default=datetime.utcnow)
    image_path = Column(String)
    quantity = Column(Integer, default=1)
    filament_code = Column(String)

    owner = relationship("User", back_populates="inventory")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "brand": self.brand,
            "material": self.material,
            "color_name": self.color_name,
            "color_hex": self.color_hex,
            "weight_initial_g": self.weight_initial_g,
            "weight_remaining_g": self.weight_remaining_g,
            "diameter": self.diameter,
            "temp_nozzle": self.temp_nozzle,
            "location": self.location,
            "date_added": self.date_added.strftime("%Y-%m-%d") if self.date_added else "",
            "image_path": self.image_path,
            "quantity": self.quantity,
            "filament_code": self.filament_code
        }

class SpoolHistory(Base):
    __tablename__ = "spool_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Original spool data (copied from Inventory)
    brand = Column(String)
    material = Column(String)
    color_name = Column(String)
    color_hex = Column(String)
    weight_initial_g = Column(Integer)
    diameter = Column(Float)
    temp_nozzle = Column(String)
    location = Column(String)
    filament_code = Column(String)
    image_path = Column(String)
    
    # History metadata
    date_added = Column(DateTime)  # When originally added to inventory
    date_consumed = Column(DateTime, default=datetime.utcnow)  # When marked as used
    
    # Relationship
    owner = relationship("User", back_populates="spool_history")
