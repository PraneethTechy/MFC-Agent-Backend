import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_overview_dashboard_integrity():
    client = TestClient(app)
    res = client.get('/api/dashboard/overview')
    assert res.status_code == 200, f'Expected 200, got {res.status_code}'
    data = res.json()

    # 1. KPI Reconciliation
    kpis = data['kpis']
    cost_cr = kpis['total_direct_cost_cr']
    unit_cost = kpis['avg_direct_cost_per_unit']
    vol = kpis['total_costed_units']
    assert abs(cost_cr - 2321.99) < 0.05, f'Cost mismatch: {cost_cr}'
    assert abs(unit_cost - 10845.91) < 1.0, f'Unit cost mismatch: {unit_cost}'
    assert abs(vol - 2140888) < 1.0, f'Volume mismatch: {vol}'

    # 2. Production Flow Reconciliation
    prod = data['production']
    tot = prod['total_produced']
    good = prod['good_output']
    rej = prod['rejected_output']
    yld = prod['yield_pct']
    assert tot == good + rej, f'Gross != Good + Rejection: {tot} vs {good + rej}'
    assert abs(yld - 98.15) < 0.05, f'Yield mismatch: {yld}'

    # 3. Category Cost Distribution
    cats = data['categories']
    total_share = sum(c['share_pct'] for c in cats)
    assert abs(total_share - 100.0) < 0.1, f'Category share != 100%: {total_share}'

    # 4. Plant Performance
    plants = data['plant_performance']
    assert len(plants) >= 4, f'Expected at least 4 plants, got {len(plants)}'
    for p in plants:
        assert p['output_units'] > 0
        assert p['yield_pct'] > 0
        assert p['cost_share_pct'] >= 0

    # 5. Hero Banner
    hero = data['hero_banner']
    assert hero['cost_change_display'] == '↓ -32.29%'
    assert hero['output_change_display'] == '↑ +3.91%'
    assert hero['yield_change_pp'] == 0.28

    # 6. Key Insights
    insights = data['intelligence_findings']
    assert len(insights) >= 3
    assert any("32.29%" in ins['explanation'] for ins in insights)
    assert any("3,832" in ins['explanation'] for ins in insights)
    assert any("SPH-PRO-256" in ins['explanation'] for ins in insights)

    # 7. Daily Trend
    daily = data['daily_trend']
    assert len(daily) == 11
    assert any(d['is_anomaly'] for d in daily)

    print('All Overview Dashboard assertions passed with 100% database verification!')

if __name__ == '__main__':
    test_overview_dashboard_integrity()
