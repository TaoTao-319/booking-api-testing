from copy import deepcopy


import requests


def test_patch_only_price(base_url, token, booking):

    url = f"{base_url}/booking/{booking['id']}"

    expected = deepcopy(booking["data"])

    expected["totalprice"] = 350


    response = requests.patch(

        url,

        json={"totalprice": 350},

        cookies={"token": token},

        timeout=5,
    )

    assert response.status_code == 200, response.text

    assert response.json() == expected, response.text


    query = requests.get(url, timeout=5)

    assert query.status_code == 200, query.text

    assert query.json() == expected, query.text


def test_patch_empty_object_rejected(base_url, token, booking):

    url = f"{base_url}/booking/{booking['id']}"


    response = requests.patch(

        url,

        json={},

        cookies={"token": token},

        timeout=5,
    )

    assert response.status_code == 400, response.text

    assert response.json() == {
        "error": "Patch body must not be empty"
    }, response.text


    query = requests.get(url, timeout=5)

    assert query.status_code == 200, query.text

    assert query.json() == booking["data"], query.text


def test_patch_unknown_field_rejected(base_url, token, booking):

    url = f"{base_url}/booking/{booking['id']}"


    response = requests.patch(

        url,

        json={"unexpected_field": "x"},

        cookies={"token": token},

        timeout=5,
    )

    assert response.status_code == 400, response.text

    assert response.json() == {
        "error": "Unknown field: unexpected_field"
    }, response.text


    query = requests.get(url, timeout=5)

    assert query.status_code == 200, query.text

    assert query.json() == booking["data"], query.text
