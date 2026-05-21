from pydantic import BaseModel, ConfigDict


class WrittenFile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)

    path: str
    content: str
