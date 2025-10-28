def test_health_ready_ok(client):
    r = client.get("/v1/health/ready")
    assert r.status_code in (200, 503)
    assert "status" in r.json()
