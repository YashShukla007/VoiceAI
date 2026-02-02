from pydantic import BaseModel


class PacketSchema(BaseModel):
    sequence: int
    data: str
    timestamp: float
