from pydantic import BaseModel
from typing import Optional, Dict, Any

class ResponseModel(BaseModel):
    code: str
    data: Any
    msg: Optional[str] = ""

async def create_response(data, code: str = "0", msg: str = "success") -> Dict[str, Any]:
    if data is None:
        data = {}
    return ResponseModel(code=code, data=data, msg=msg).dict()