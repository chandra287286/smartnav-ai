from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.database.session import init_db
from app.routes import auth, navigation, places, routes_api, search, user_data

settings = get_settings()
setup_logging(settings.DEBUG)
logger = logging.getLogger("smartnav.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing SmartNav AI database and services...")
    init_db()
    yield
    logger.info("Shutting down SmartNav AI backend.")


app = FastAPI(
    title="SmartNav AI API",
    description="Full-stack GPS navigation backend powered by FastAPI, PostGIS, Nominatim, OSRM, and Overpass.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(routes_api.router)
app.include_router(places.router)
app.include_router(navigation.router)
app.include_router(user_data.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
