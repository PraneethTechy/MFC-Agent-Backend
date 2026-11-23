"""
Tests for Global Manufacturing Intelligence Search.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.search.service import GlobalSearchService


@pytest.fixture
def client():
    return TestClient(app)


def test_is_question_detection():
    """Verify natural-language analytical questions are accurately identified."""
    assert GlobalSearchService.is_question("Why did manufacturing cost increase by 7.87%?") is True
    assert GlobalSearchService.is_question("Which product has highest cost?") is True
    assert GlobalSearchService.is_question("Compare manufacturing costs between plants") is True
    assert GlobalSearchService.is_question("What are the major contributors to scrap and rework?") is True
    assert GlobalSearchService.is_question("How is material price affecting unit cost?") is True
    assert GlobalSearchService.is_question("Is production rejection affecting yield?") is True
    assert GlobalSearchService.is_question("Explain largest unresolved variance") is True

    # Entities should NOT be treated as questions
    assert GlobalSearchService.is_question("SPH-PRO-256") is False
    assert GlobalSearchService.is_question("NAND Flash") is False
    assert GlobalSearchService.is_question("FAL-L1") is False
    assert GlobalSearchService.is_question("Direct Material") is False


def test_global_search_product_query(client):
    """GET /api/search/global returns product matches with actual direct costs."""
    res = client.get("/api/search/global?q=SPH-PRO")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] > 0
    assert "PRODUCTS" in data["categories"]
    products = data["categories"]["PRODUCTS"]
    assert any("SPH-PRO-256" in p["title"] for p in products)
    item = next(p for p in products if "SPH-PRO-256" in p["title"])
    assert item["entity_type"] == "PRODUCT"
    assert item["navigation_target"]["tab"] == "product-analysis"
    assert item["navigation_target"]["params"]["product"] == "SPH-PRO-256"
    assert "unit" in item["relevant_metric"].lower()


def test_global_search_material_component_query(client):
    """GET /api/search/global returns materials and components."""
    res = client.get("/api/search/global?q=NAND")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] > 0
    assert "MATERIALS_COMPONENTS" in data["categories"]
    comps = data["categories"]["MATERIALS_COMPONENTS"]
    assert any("NAND" in c["title"] for c in comps)
    item = next(c for c in comps if "NAND" in c["title"])
    assert item["navigation_target"]["tab"] == "component-analysis"


def test_global_search_cost_analysis_query(client):
    """GET /api/search/global returns cost categories."""
    res = client.get("/api/search/global?q=variance")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] > 0
    assert "COST_ANALYSIS" in data["categories"]
    costs = data["categories"]["COST_ANALYSIS"]
    assert any("Variance" in c["title"] for c in costs)


def test_global_search_production_line_query(client):
    """GET /api/search/global returns lines and facilities."""
    res = client.get("/api/search/global?q=FAL-L1")
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] > 0
    assert "PRODUCTION_QUALITY" in data["categories"]
    facs = data["categories"]["PRODUCTION_QUALITY"]
    assert any("FAL-L1" in f["title"] for f in facs)


def test_global_search_question_classification(client):
    """GET /api/search/global classifies question and returns suggested_investigation."""
    query = "Why did manufacturing cost increase by 7.87% in November 2026?"
    res = client.get(f"/api/search/global?q={query}")
    assert res.status_code == 200
    data = res.json()
    assert data["is_question"] is True
    assert data["suggested_investigation"] == query

