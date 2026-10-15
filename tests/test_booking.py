from copy import deepcopy


import requests


def test_create_booking(booking):

    response = booking["response"]

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["bookingid"] == booking["id"], data


    assert data["booking"] == booking["data"], data


def test_list_bookings(base_url, booking):

    response = requests.get(f"{base_url}/booking", timeout=5)

    assert response.status_code == 200, response.text

    data = response.json()

    assert isinstance(data, list), data

    assert {"bookingid": booking["id"]} in data, data


def test_get_booking(base_url, booking):

    response = requests.get(
        f"{base_url}/booking/{booking['id']}",
        timeout=5,
    )

    assert response.status_code == 200, response.text

    assert response.json() == booking["data"], response.text


def test_filter_booking_by_name(base_url, booking):

    response = requests.get(
        f"{base_url}/booking",
        params={
            "firstname": booking["data"]["firstname"],
            "lastname": booking["data"]["lastname"],
        },
        timeout=5,
    )

    assert response.status_code == 200, response.text

    assert response.json() == [{"bookingid": booking["id"]}], response.text


    unmatched_response = requests.get(
        f"{base_url}/booking",
        params={
            "firstname": booking["data"]["firstname"],
            "lastname": booking["data"]["lastname"] + "_missing",
        },
        timeout=5,
    )

    assert unmatched_response.status_code == 200, unmatched_response.text

    assert unmatched_response.json() == [], unmatched_response.text


def test_put_booking(base_url, token, booking):

    updated_data = deepcopy(booking["data"])

    assert updated_data["totalprice"] == 200, updated_data

    updated_data["totalprice"] = 300


    response = requests.put(
        f"{base_url}/booking/{booking['id']}",
        json=updated_data,
        cookies={"token": token},
        timeout=5,
    )

    assert response.status_code == 200, response.text

    assert response.json() == updated_data, response.text


    query_response = requests.get(
        f"{base_url}/booking/{booking['id']}",
        timeout=5,
    )

    assert query_response.status_code == 200, query_response.text

    assert query_response.json() == updated_data, query_response.text


def test_delete_booking(base_url, token, booking):

    response = requests.delete(
        f"{base_url}/booking/{booking['id']}",
        cookies={"token": token},
        timeout=5,
    )

    assert response.status_code == 201, response.text

    assert response.json() == {"message": "Booking deleted"}, response.text
