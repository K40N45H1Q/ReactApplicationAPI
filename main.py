from os import getenv
from httpx import AsyncClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

# --- ENV & TELEGRAM ---
load_dotenv()
BOT_TOKEN = getenv("BOT_TOKEN")

BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

api = FastAPI()

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔐 Лучше заменить * на ['http://localhost:3000'] в продакшене
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.get("/avatar/{user_id}")
async def get_avatar(user_id: int):
    async with AsyncClient() as client:
        resp_photos = await client.get(f"{BOT_API}/getUserProfilePhotos", params={"user_id": user_id, "limit": 1})
        data = resp_photos.json()

        if not data.get("ok") or not data["result"]["total_count"]:
            raise HTTPException(status_code=404, detail="Avatar not found")

        file_id = data["result"]["photos"][0][0]["file_id"]
        resp_file = await client.get(f"{BOT_API}/getFile", params={"file_id": file_id})
        file_data = resp_file.json()

        if not file_data.get("ok"):
            raise HTTPException(500, detail="Failed to get file info")

        file_url = f"{FILE_API}/{file_data['result']['file_path']}"
        file_resp = await client.get(file_url)

        if file_resp.status_code != 200:
            raise HTTPException(502, detail="Failed to download avatar")

        return StreamingResponse(file_resp.aiter_bytes(), media_type="image/jpeg")


# --- DATABASE SETUP ---
DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Category(Base):
    __tablename__ = "categories"
    name = Column(String, primary_key=True)
    products = relationship("Product", back_populates="category", cascade="all, delete")

class Product(Base):
    __tablename__ = "products"
    name = Column(String, primary_key=True)
    price = Column(Float, nullable=False)
    category_name = Column(String, ForeignKey("categories.name", ondelete="CASCADE"))
    category = relationship("Category", back_populates="products")

Base.metadata.create_all(bind=engine)

# --- SCHEMAS ---
class CategoryCreate(BaseModel):
    name: str

class CategoryResponse(CategoryCreate):
    products_count: int = 0
    model_config = {"from_attributes": True}

class ProductCreate(BaseModel):
    name: str
    price: float
    category_name: str

class ProductResponse(ProductCreate):
    model_config = {"from_attributes": True}

# --- DEPENDENCY ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- CATEGORY ENDPOINTS ---
@api.post("/categories/", response_model=CategoryResponse, status_code=201)
def create_category(cat: CategoryCreate, db: Session = Depends(get_db)):
    if db.query(Category).filter_by(name=cat.name).first():
        raise HTTPException(400, "Category already exists")
    category = Category(name=cat.name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryResponse(name=category.name, products_count=0)

@api.get("/categories/", response_model=List[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return [CategoryResponse(name=c.name, products_count=len(c.products)) for c in db.query(Category).all()]

@api.delete("/categories/{name}", status_code=204)
def delete_category(name: str, db: Session = Depends(get_db)):
    category = db.query(Category).filter_by(name=name).first()
    if not category:
        raise HTTPException(404, "Category not found")
    db.delete(category)
    db.commit()

# --- PRODUCT ENDPOINTS ---
@api.post("/products/", response_model=ProductResponse, status_code=201)
def create_product(prod: ProductCreate, db: Session = Depends(get_db)):
    if not db.query(Category).filter_by(name=prod.category_name).first():
        raise HTTPException(400, "Category does not exist")
    product = Product(**prod.dict())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

@api.get("/products/", response_model=List[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

@api.get("/categories/{name}/products", response_model=List[ProductResponse])
def list_products_by_category(name: str, db: Session = Depends(get_db)):
    if not db.query(Category).filter_by(name=name).first():
        raise HTTPException(404, "Category not found")
    return db.query(Product).filter_by(category_name=name).all()

@api.delete("/products/{name}", status_code=204)
def delete_product(name: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter_by(name=name).first()
    if not product:
        raise HTTPException(404, "Product not found")
    db.delete(product)
    db.commit()