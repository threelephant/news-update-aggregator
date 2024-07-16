from pydantic import BaseModel
from typing import List


class UserPreferences(BaseModel):
    username: str
    preferences: List[str]
