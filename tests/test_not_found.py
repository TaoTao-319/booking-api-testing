from copy import deepcopy


import pytest

import requests


@pytest.fixture
def deleted_booking(base_url, token, booking):

    response = requests.delete(
        f"{base_url}/booking/{booking['id']}",
        cookies={"token": token},
        timeout=5,
    )

    assert response.status_code == 201, response.text

    assert response.json() == {"message": "Booking deleted"}, response.text


    return booking


def test_get_deleted_booking(base_url, deleted_booking):

    response = requests.get(
        f"{base_url}/booking/{deleted_booking['id']}", timeout=5
    )

    assert response.status_code == 404, response.text

    assert response.json() == {"error": "Booking or endpoint not found"}, response.text


def test_put_deleted_booking(base_url, token, deleted_booking):

    updated_data = deepcopy(deleted_booking["data"])

    updated_data["totalprice"] = 300

    response = requests.put(
        f"{base_url}/booking/{deleted_booking['id']}",
        json=updated_data,
        cookies={"token": token},
        timeout=5,
    )

    assert response.status_code == 404, response.text

    assert response.json() == {"error": "Booking not found"}, response.text


def test_delete_deleted_booking(base_url, token, deleted_booking):

    response = requests.delete(
        f"{base_url}/booking/{deleted_booking['id']}",
        cookies={"token": token},
        timeout=5,
    )

    assert response.status_code == 404, response.text

    assert response.json() == {"error": "Booking not found"}, response.text
