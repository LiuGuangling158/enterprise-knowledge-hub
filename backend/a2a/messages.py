from pydantic import BaseModel


class A2AMessage(BaseModel):
    sender: str
    receiver: str
    task_id: str
    type: str
    payload: dict
    protocol: str = "a2a/v1"
