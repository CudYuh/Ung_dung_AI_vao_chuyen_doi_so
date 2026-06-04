from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import questions_and_answers, products, valuation_api, wiki, domain_registry_api
import models
from database import engine


APP_DESCRIPTION = """
A modern web application built with FastAPI that combines AI-powered valuation,
PostgreSQL database backend, and LLM Wiki / Second Brain knowledge framework.

Key Features:
- RESTful API endpoints built with FastAPI
- PostgreSQL database integration using SQLAlchemy ORM
- AI valuation using Ollama (local) and Tavily
- Product search and approval workflow
- LLM Wiki framework for knowledge organization
- Markdown entity pages, concept pages, search index, and graph relationships
"""


app = FastAPI(
    title="AI Valuation System with LLM Wiki",
    description=APP_DESCRIPTION,
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


try:
    models.base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not create database tables: {e}")
    print("The application will continue to run, but database tables may not exist.")


app.include_router(router=questions_and_answers.router)
app.include_router(router=products.router)
app.include_router(router=valuation_api.router)
app.include_router(router=wiki.router)
app.include_router(router=domain_registry_api.router)


@app.get("/")
async def root():
    return {
        "message": "AI Valuation System is running",
        "modules": [
            "Products",
            "Valuation AI",
            "LLM Wiki / Second Brain",
        ],
    }