def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_feedback_persists_and_is_returned_by_api(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Feedback Test Candidate"}).json()["id"]
    interview = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "scheduled_date": "2026-08-14T10:00:00", "interviewer": "Garima Sharma",
    }).json()

    resp = client.put(f"/api/interviews/{interview['id']}", json={
        "overall_rating": 4, "technical_rating": 5, "communication_rating": 3, "culture_fit_rating": 4,
        "strengths": "Strong technical fundamentals", "weaknesses": "Limited leadership experience",
        "observations": "Confident, asked good questions", "recommendation": "Hire", "status": "Completed",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_rating"] == 4
    assert body["recommendation"] == "Hire"
    assert body["strengths"] == "Strong technical fundamentals"

    # Confirm it's actually persisted, not just echoed back from the request.
    refetched = client.get("/api/interviews/", params={"candidate_id": candidate_id}).json()
    assert refetched[0]["recommendation"] == "Hire"
    assert refetched[0]["overall_rating"] == 4


def test_rating_out_of_range_rejected(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Rating Range Candidate"}).json()["id"]
    interview = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "scheduled_date": "2026-08-14T10:00:00",
    }).json()

    resp = client.put(f"/api/interviews/{interview['id']}", json={"overall_rating": 7})
    assert resp.status_code == 422


def test_invalid_recommendation_rejected(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Bad Recommendation Candidate"}).json()["id"]
    interview = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "scheduled_date": "2026-08-14T10:00:00",
    }).json()

    resp = client.put(f"/api/interviews/{interview['id']}", json={"recommendation": "Maybe"})
    assert resp.status_code == 422


def test_interview_still_gets_business_id(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Interview Business ID Candidate"}).json()["id"]
    resp = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "scheduled_date": "2026-08-14T10:00:00",
    })
    assert resp.status_code == 201
    assert len(resp.json()["business_id"]) == 10
