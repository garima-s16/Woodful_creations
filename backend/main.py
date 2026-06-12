from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from datetime import datetime, timedelta
import jwt
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import json

load_dotenv()

app = FastAPI(
    title="Woodful Creations API",
    description="AI-powered business management system",
    version="1.0.0"
)

security = HTTPBearer()

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "woodful-secret-key-change-in-production")

in_memory_db = {
    "products": [
        {"id": 1, "name": "Walnut Wood", "category": "Wood", "quantity": 150, "minQuantity": 50, "price": 500, "unit": "pieces", "lastUpdated": str(datetime.now())},
        {"id": 2, "name": "Oak Wood", "category": "Wood", "quantity": 20, "minQuantity": 50, "price": 450, "unit": "pieces", "lastUpdated": str(datetime.now())},
        {"id": 3, "name": "Hardware Set", "category": "Hardware", "quantity": 200, "minQuantity": 100, "price": 150, "unit": "sets", "lastUpdated": str(datetime.now())},
        {"id": 4, "name": "Wood Stain", "category": "Finishing", "quantity": 80, "minQuantity": 30, "price": 250, "unit": "liters", "lastUpdated": str(datetime.now())},
    ],
    "users": [
        {"id": "user1", "email": "nikhil@woodful.com", "password": "nikhil123", "name": "Nikhil", "role": "master"},
        {"id": "user2", "email": "garima@woodful.com", "password": "garima123", "name": "Garima", "role": "master"},
        {"id": "user3", "email": "user@woodful.com", "password": "user123", "name": "User", "role": "user"},
    ]
}

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: dict

class Product(BaseModel):
    name: str
    category: str
    quantity: int
    minQuantity: int
    price: float
    unit: str

class UpdateProduct(BaseModel):
    quantity: Optional[int] = None
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None

class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str

def create_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_token(credentials: HTTPAuthCredentials):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/")
def read_root():
    return {
        "message": "Woodful Creations API",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    user = None
    for u in in_memory_db["users"]:
        if u["email"] == request.email and u["password"] == request.password:
            user = u
            break
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token({"user_id": user["id"], "email": user["email"], "role": user["role"]})
    
    return LoginResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"]
        }
    )

@app.get("/api/dashboard")
def get_dashboard(credentials: HTTPAuthCredentials = Depends(security)):
    verify_token(credentials)
    
    products = in_memory_db["products"]
    low_stock = [p for p in products if p["quantity"] <= p["minQuantity"]]
    
    stats = {
        "totalProducts": len(products),
        "lowStockItems": len(low_stock),
        "pendingEstimates": 5,
        "activeClients": 8,
        "pendingPayments": 12000
    }
    
    recent_activity = [
        {"id": 1, "type": "inventory", "message": "Walnut wood stock updated", "timestamp": str(datetime.now())},
        {"id": 2, "type": "estimate", "message": "Estimate created for client", "timestamp": str(datetime.now())},
        {"id": 3, "type": "client", "message": "New client added", "timestamp": str(datetime.now())},
    ]
    
    return {
        "stats": stats,
        "recentActivity": recent_activity
    }

@app.get("/api/inventory")
def get_inventory(credentials: HTTPAuthCredentials = Depends(security)):
    verify_token(credentials)
    return in_memory_db["products"]

@app.post("/api/inventory")
def add_inventory(product: Product, credentials: HTTPAuthCredentials = Depends(security)):
    verify_token(credentials)
    
    new_product = {
        "id": max([p["id"] for p in in_memory_db["products"]]) + 1 if in_memory_db["products"] else 1,
        "name": product.name,
        "category": product.category,
        "quantity": product.quantity,
        "minQuantity": product.minQuantity,
        "price": product.price,
        "unit": product.unit,
        "lastUpdated": str(datetime.now())
    }
    
    in_memory_db["products"].append(new_product)
    return new_product

@app.patch("/api/inventory/{product_id}")
def update_inventory(product_id: int, update: UpdateProduct, credentials: HTTPAuthCredentials = Depends(security)):
    verify_token(credentials)
    
    for product in in_memory_db["products"]:
        if product["id"] == product_id:
            if update.quantity is not None:
                product["quantity"] = update.quantity
            if update.name is not None:
                product["name"] = update.name
            if update.category is not None:
                product["category"] = update.category
            if update.price is not None:
                product["price"] = update.price
            
            product["lastUpdated"] = str(datetime.now())
            return product
    
    raise HTTPException(status_code=404, detail="Product not found")

@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatMessage, credentials: HTTPAuthCredentials = Depends(security)):
    verify_token(credentials)
    
    message = request.message.lower()
    
    if "inventory" in message or "stock" in message:
        response = "You have 4 products in inventory. 1 product (Oak Wood) is running low on stock. Would you like to reorder?"
    elif "low stock" in message or "alert" in message:
        response = "Alert: Oak Wood is below minimum quantity. Current: 20, Minimum: 50. Recommend ordering immediately."
    elif "product" in message:
        response = "Your inventory includes Walnut Wood, Oak Wood, Hardware Set, and Wood Stain. Total inventory value is approximately Rs 180,500."
    elif "estimate" in message or "quote" in message:
        response = "You have 5 pending estimates. Would you like to create a new estimate or view existing ones?"
    elif "client" in message:
        response = "You have 8 active clients. Would you like to view client details or manage their orders?"
    elif "help" in message:
        response = "I can help you with inventory management, estimates, client information, and order tracking. What would you like to know?"
    else:
        response = f"You asked about: {request.message}. I can assist with inventory, estimates, clients, and orders. How can I help you further?"
    
    return ChatResponse(response=response)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Woodful Creations Backend API"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)