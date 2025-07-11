from typing import List, Optional, Dict, Any
from datetime import datetime
from .base_schemas import BaseInterface, RequestType

class InterfaceCreate(BaseInterface):
    pass

class InterfaceUpdate(BaseInterface):
    pass

class InterfaceRead(BaseInterface):
    id: str
    module_id: str

    class Config:
        from_attributes = True

