from fastapi import FastAPI

from app import models  # noqa: F401  (registers the tables)
from app.database import Base, engine
from app.errors import register_exception_handlers
from app.seed import seed_admin
from app.routers import attempts, auth, credits, quizzes

Base.metadata.create_all(bind=engine)
seed_admin()

app = FastAPI(
    title="Quiz API with Credit System",
    version="1.0.0",
    description="Quiz application REST API with a stake-and-reward credit system.",
)


register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(attempts.router)
app.include_router(credits.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}