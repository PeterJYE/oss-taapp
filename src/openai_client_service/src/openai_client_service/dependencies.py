from fastapi import Header, HTTPException, status

async def get_subject(x_subject: str | None = Header(default=None)) -> str:
    if not x_subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Subject header")
    return x_subject
