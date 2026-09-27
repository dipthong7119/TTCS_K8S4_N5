from typing import Literal

from pydantic import BaseModel


class ResetRequest(BaseModel):
    type: Literal["Soft", "Hard"] = "Soft"
