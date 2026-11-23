"""
Pydantic schemas for Global Manufacturing Intelligence Search.
"""

from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


class SearchNavigationTarget(BaseModel):
    tab: str
    params: Dict[str, Any] = Field(default_factory=dict)


class SearchResultItem(BaseModel):
    id: str
    entity_type: str  # PRODUCT, MATERIAL, COMPONENT, COST_RECORD, PRODUCTION_LINE, QUALITY_DEFECT, PLANT
    category: str  # PRODUCTS, MATERIALS_COMPONENTS, COST_ANALYSIS, PRODUCTION_QUALITY
    title: str
    subtitle: str
    description: Optional[str] = None
    relevant_metric: Optional[str] = None
    badge: Optional[str] = None
    navigation_target: SearchNavigationTarget


class GlobalSearchResponse(BaseModel):
    query: str
    is_question: bool = False
    suggested_investigation: Optional[str] = None
    total_matches: int = 0
    categories: Dict[str, List[SearchResultItem]] = Field(default_factory=dict)

