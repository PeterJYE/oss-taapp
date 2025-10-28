from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()  # read .env for keys/urls

from openai_client_impl import init_db  # type: ignore
from .routes import oauth, ai

app = FastAPI(title="OpenAI Client Service", version="0.1.0")

# init lightweight storage on startup (creates .data/app.db if using storage later)
init_db()

app.include_router(oauth.router, prefix="/auth", tags=["OAuth"])
app.include_router(ai.router, prefix="/ai", tags=["AI"])

@app.get("/health")
def health():
    return {"status": "ok"}
