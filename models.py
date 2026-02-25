from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# --- SQLAlchemy Models ---
class UserModel(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class ProductModel(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_base64 = db.Column(db.Text, nullable=True) # Storing image as Base64 string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Pydantic Schemas (for Validation) ---
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class ProductBase(BaseModel):
    name: str
    description: str
    price: float = Field(gt=0)
    category: str
    image_base64: Optional[str] = None # Expecting base64 string or null

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int
    created_at: datetime

class CartItem(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)

class CheckoutRequest(BaseModel):
    payment_method: str
    address: str

class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
