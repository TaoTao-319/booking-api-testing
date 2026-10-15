import requests


def test_ping(base_url):

    response = requests.get(f"{base_url}/ping", timeout=5)


    assert response.status_code == 200, response.text


    data = response.json()

    assert data["status"] == "ok", data
