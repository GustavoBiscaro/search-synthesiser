from typing import List
from pydantic import BaseModel
from typing_extensions import Annotated
import operator


class QueryResult(BaseModel):
    title: str
    url: str
    resume: str


class ReportState(BaseModel):
    user_input: str
    queries: List[str] = []
    query_results: Annotated[List[QueryResult], operator.add] = []  # <-- acumula resultados
    final_response: str = ""
