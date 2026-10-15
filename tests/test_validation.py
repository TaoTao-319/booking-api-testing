import json

from copy import deepcopy

from pathlib import Path


import pytest

import requests


EXPECTED_STATUS = 400


@pytest.fixture
def valid_booking_data():

    template_path = Path(__file__).resolve().parent / "data" / "booking.json"

    return json.loads(template_path.read_text(encoding="utf-8"))


def _make_invalid_payload(valid_booking_data, action, field_path, value):

    payload = deepcopy(valid_booking_data)


    target = payload

    for key in field_path[:-1]:

        target = target[key]

    field_name = field_path[-1]


    if action == "remove":

        del target[field_name]
    elif action == "set":

        target[field_name] = value
    else:

        raise ValueError(f"不支持的输入修改操作：{action}")

    return payload


@pytest.mark.parametrize(
    "action, field_path, value, expected_error",
    [

        pytest.param(
            "remove", ("firstname",), None,
            "Missing field: firstname",
            id="missing_firstname",
        ),

        pytest.param(
            "remove", ("bookingdates", "checkout"), None,
            "Missing or invalid bookingdates.checkout",
            id="missing_checkout",
        ),

        pytest.param(
            "set", ("totalprice",),
            "200",
            "Incorrect type: totalprice",
            id="price_wrong_type",
        ),

        pytest.param(
            "set", ("depositpaid",),
            "true",
            "Incorrect type: depositpaid",
            id="deposit_wrong_type",
        ),

        pytest.param(
            "set", ("totalprice",), -1,
            "totalprice must be greater than or equal to 0",
            id="negative_price",
        ),

        pytest.param(
            "set", ("firstname",), "   ",
            "Must not be blank: firstname",
            id="blank_firstname",
        ),

        pytest.param(
            "set", ("bookingdates", "checkout"), "2026-02-30",
            "Invalid date: bookingdates.checkout (use YYYY-MM-DD)",
            id="invalid_checkout_date",
        ),
    ],
)
def test_booking_input_validation(
    base_url, valid_booking_data, action, field_path, value, expected_error
):

    payload = _make_invalid_payload(valid_booking_data, action, field_path, value)


    response = requests.post(
        f"{base_url}/booking",
        json=payload,
        timeout=5,
    )

    assert response.status_code == EXPECTED_STATUS, response.text


    actual_error = response.json()["error"]

    assert actual_error == expected_error, response.text


def test_invalid_json_body(base_url):

    raw_body = '{"firstname":"Alex",}'


    response = requests.post(
        f"{base_url}/booking",
        data=raw_body,
        headers={"Content-Type": "application/json"},
        timeout=5,
    )


    assert response.status_code == EXPECTED_STATUS, response.text

    assert response.json() == {"error": "Invalid JSON body"}, response.text
