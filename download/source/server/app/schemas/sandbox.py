from pydantic import BaseModel, Field


class CodeRunRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = 'python'
    timeout: int = 10


class CodeRunResponse(BaseModel):
    output: str
    error: str = ''
    exit_code: int = 0
    execution_time: float = 0.0
