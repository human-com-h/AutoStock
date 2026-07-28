from pydantic import BaseModel


class RestoreRequest(BaseModel):
    name: str
    confirm: str
