from copy import deepcopy


import pytest

import requests


EXPECTED_LOGIN_STATUS = 401


EXPECTED_FORBIDDEN_STATUS = 403


INVALID_COOKIES = {"token": "invalid-token"}


def _assert_booking_unchanged(base_url, booking):

    expected_data = booking["data"]


    query_response = requests.get(
        f"{base_url}/booking/{booking['id']}", timeout=5
    )

    assert query_response.status_code == 200, query_response.text

    assert query_response.json() == expected_data, query_response.text


def test_login_with_wrong_password(base_url):

    response = requests.post(
        f"{base_url}/auth",
        json={"username": "admin", "password": "wrong-password"},
        timeout=5,
    )

    assert response.status_code == EXPECTED_LOGIN_STATUS, response.text

    data = response.json()

    assert data.get("error") == "Bad credentials", data


    token_absent = "token" not in data

    assert token_absent, data


@pytest.mark.parametrize(
    "method, credential_kind",
    [
        pytest.param("PUT", "missing", id="put_without_token"),
        pytest.param("PUT", "invalid", id="put_with_invalid_token"),
        pytest.param("DELETE", "missing", id="delete_without_token"),
        pytest.param("DELETE", "invalid", id="delete_with_invalid_token"),
    ],
)
def test_booking_rejects_bad_credentials(base_url, booking, method, credential_kind):

    if credential_kind == "missing":
        cookies = {}
    else:

        cookies = INVALID_COOKIES


    request_options = {"cookies": cookies, "timeout": 5}

    if method == "PUT":

        updated_data = deepcopy(booking["data"])

        assert updated_data["totalprice"] == 200, updated_data

        updated_data["totalprice"] = 300

        request_options["json"] = updated_data


    response = requests.request(
        method,
        f"{base_url}/booking/{booking['id']}",
        **request_options,
    )

    assert response.status_code == EXPECTED_FORBIDDEN_STATUS, response.text

    assert response.json() == {"error": "A valid token cookie is required"}, response.text

    _assert_booking_unchanged(base_url, booking)


def test_logged_out_token_cannot_update_booking(base_url, auth_booking_factory):

    with auth_booking_factory(base_url) as booking:

        dedicated_token = booking["token"]

        logout_response = requests.delete(
            f"{base_url}/auth", cookies={"token": dedicated_token}, timeout=5
        )

        assert logout_response.status_code == 200, logout_response.text

        assert logout_response.json() == {"message": "Logged out"}, logout_response.text


        revoked_cookies = {"token": dedicated_token}


        updated_data = deepcopy(booking["data"])

        updated_data["totalprice"] = 300

        response = requests.put(
            f"{base_url}/booking/{booking['id']}",
            json=updated_data,
            cookies=revoked_cookies,
            timeout=5,
        )

        assert response.status_code == EXPECTED_FORBIDDEN_STATUS, response.text

        assert response.json() == {"error": "A valid token cookie is required"}, response.text

        _assert_booking_unchanged(base_url, booking)


def test_logged_out_token_cannot_delete_booking(base_url, auth_booking_factory):

    with auth_booking_factory(base_url) as booking:

        old_token = booking["token"]

        logout = requests.delete(
            f"{base_url}/auth", cookies={"token": old_token}, timeout=5
        )

        assert logout.status_code == 200, logout.text

        assert logout.json() == {"message": "Logged out"}, logout.text


        response = requests.delete(

            f"{base_url}/booking/{booking['id']}",

            cookies={"token": old_token},

            timeout=5,
        )

        assert response.status_code == EXPECTED_FORBIDDEN_STATUS, response.text

        assert response.json() == {
            "error": "A valid token cookie is required"
        }, response.text

        _assert_booking_unchanged(base_url, booking)

