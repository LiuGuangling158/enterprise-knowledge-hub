from typing import Annotated

from fastapi import Depends, Header, HTTPException

from core.security import decode_access_token
from services.document_service import DocumentService


documents = DocumentService()


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录")

    payload = decode_access_token(authorization.split(" ", 1)[1])
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="登录状态已失效")

    user = documents.get_user(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]
