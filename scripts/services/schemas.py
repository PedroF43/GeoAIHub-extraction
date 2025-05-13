from typing import List, Optional
from pydantic import BaseModel


class PaperMetadata(BaseModel):
    title: str
    authors: str
    keywords: str
    doi: str
    year: Optional[int] = None
    journal: Optional[str] = None
    page_number: int
    extraction_time: Optional[float] = None


class PostPaperMetadata(PaperMetadata):
    location_number: int


class PostPaperLocationData(BaseModel):
    location_names: List[str] = []
    location_frequencies: List[int] = []
    location_importance_scores: List[int] = []
    location_number: int
    extraction_time: Optional[float] = None


class Keywords(BaseModel):
    keyword_name: str


class Authors(BaseModel):
    author_name: str


class Metadata(BaseModel):
    paper_title: str
    authors: List[Authors]
    journal_name: str
    keywords: List[Keywords]
    publication_year: str
    doi_number: str


class location_name(BaseModel):
    location_name: str
    location_country: str
    importance_score: int = 5  # Default value, must be between 1-10

    def __init__(self, location_name: str, importance_score: int = 5):
        super().__init__(location_name=location_name)
        if not 1 <= importance_score <= 10:
            raise ValueError("importance_score must be between 1 and 10")
        self.importance_score = importance_score


class coordinates(BaseModel):
    latitude: str
    longitude: str


class Locations(BaseModel):
    locations: List[location_name]
