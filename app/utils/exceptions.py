from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.utils.response import create_response

async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=await create_response(data={}, code=str(exc.status_code), msg=exc.detail)
    )