import requests


TIMEOUT = 5


def test_login_query_and_logout(base_url):

    login_response = requests.post(
        f"{base_url}/auth",
        json={"username": "admin", "password": "password123"},
        timeout=TIMEOUT,
    )

    assert login_response.status_code == 200, login_response.text


    login_data = login_response.json()

    token = login_data["token"]

    assert isinstance(token, str) and token, "登录响应必须包含非空字符串 token"


    try:

        query_response = requests.get(
            f"{base_url}/booking",
            params={"firstname": "Alex"},
            timeout=TIMEOUT,
        )

        assert query_response.status_code == 200, query_response.text


        bookings = query_response.json()

        assert isinstance(bookings, list), bookings

        for booking in bookings:

            assert isinstance(booking, dict), booking

            assert type(booking.get("bookingid")) is int, booking

            assert booking["bookingid"] > 0, booking
    finally:

        logout_response = requests.delete(
            f"{base_url}/auth",
            cookies={"token": token},
            timeout=TIMEOUT,
        )

        assert logout_response.status_code == 200, logout_response.text

        assert logout_response.json() == {"message": "Logged out"}
