from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, fests, events

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CampusHive API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel domain before submission
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(fests.router)
app.include_router(events.router)


@app.get("/")
def root():
    return {"status": "CampusHive API is running"}
