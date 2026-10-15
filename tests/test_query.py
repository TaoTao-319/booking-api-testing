from uuid import uuid4


import pytest

import requests


@pytest.fixture
def query_bookings(booking_factory):

    name_params = {"firstname": "QueryLearner", "lastname": f"Query_{uuid4().hex}"}

    cases = [
        (100, True, "2026-11-01", "2026-11-03"),
        (200, False, "2026-11-02", "2026-11-04"),
        (300, True, "2026-11-02", "2026-11-05"),
    ]

    bookings = []

    for price, deposit_paid, checkin, checkout in cases:

        booking = booking_factory(
            **name_params,
            totalprice=price,
            depositpaid=deposit_paid,
            bookingdates={"checkin": checkin, "checkout": checkout},
        )

        bookings.append(booking)

    return {"name_params": name_params, "bookings": bookings}


def _booking_ids(data):

    assert isinstance(data, list), data

    assert all(
        isinstance(item, dict) and set(item) == {"bookingid"} for item in data
    ), data

    ids = [item["bookingid"] for item in data]

    assert all(type(booking_id) is int and booking_id > 0 for booking_id in ids), data

    return ids


def test_query_without_pagination(base_url, query_bookings):

    response = requests.get(
        f"{base_url}/booking", params=query_bookings["name_params"], timeout=5
    )

    assert response.status_code == 200, response.text

    actual_ids = _booking_ids(response.json())

    expected_ids = [booking["id"] for booking in query_bookings["bookings"]]

    assert sorted(actual_ids) == sorted(expected_ids), response.text


@pytest.mark.parametrize(
    "depositpaid, expected_indexes",
    [
        pytest.param("true", (0, 2), id="name_and_paid"),
        pytest.param("false", (1,), id="name_and_unpaid"),
    ],
)
def test_filter_by_name_and_deposit(base_url, query_bookings, depositpaid, expected_indexes):

    params = query_bookings["name_params"].copy()

    params["depositpaid"] = depositpaid

    response = requests.get(f"{base_url}/booking", params=params, timeout=5)

    assert response.status_code == 200, response.text

    actual_ids = _booking_ids(response.json())

    expected_ids = [query_bookings["bookings"][index]["id"] for index in expected_indexes]

    assert sorted(actual_ids) == sorted(expected_ids), response.text


def test_filter_by_price_range(base_url, query_bookings):

    params = query_bookings["name_params"].copy()

    params.update({"min_price": 200, "max_price": 300})

    response = requests.get(f"{base_url}/booking", params=params, timeout=5)

    assert response.status_code == 200, response.text

    actual_ids = _booking_ids(response.json())

    expected_ids = [query_bookings["bookings"][index]["id"] for index in (1, 2)]

    assert sorted(actual_ids) == sorted(expected_ids), response.text


@pytest.mark.parametrize(
    "date_filters, expected_indexes",
    [
        pytest.param({"checkin": "2026-11-02"}, (1, 2), id="checkin"),
        pytest.param({"checkout": "2026-11-03"}, (0,), id="checkout"),
        pytest.param(
            {"checkin": "2026-11-02", "checkout": "2026-11-04"},
            (1,),
            id="checkin_and_checkout",
        ),
    ],
)
def test_filter_by_dates(base_url, query_bookings, date_filters, expected_indexes):

    params = query_bookings["name_params"].copy()

    params.update(date_filters)

    response = requests.get(f"{base_url}/booking", params=params, timeout=5)

    assert response.status_code == 200, response.text

    actual_ids = _booking_ids(response.json())

    expected_ids = [query_bookings["bookings"][index]["id"] for index in expected_indexes]

    assert sorted(actual_ids) == sorted(expected_ids), response.text


def test_pagination_and_completeness(base_url, query_bookings):

    all_ids = []

    for page, expected_count in ((1, 2), (2, 1), (3, 0)):

        params = query_bookings["name_params"].copy()

        params.update({"page": page, "page_size": 2})

        response = requests.get(f"{base_url}/booking", params=params, timeout=5)

        assert response.status_code == 200, response.text

        data = response.json()

        assert isinstance(data, dict), data

        assert set(data) == {"total", "page", "page_size", "bookings"}, data

        assert all(type(data[key]) is int for key in ("total", "page", "page_size")), data

        assert data["total"] == 3, data

        assert data["page"] == page, data

        assert data["page_size"] == 2, data

        page_ids = _booking_ids(data["bookings"])

        assert len(page_ids) == expected_count, data

        all_ids.extend(page_ids)

    expected_ids = {booking["id"] for booking in query_bookings["bookings"]}

    assert len(all_ids) == 3, all_ids

    assert len(all_ids) == len(set(all_ids)), all_ids

    assert set(all_ids) == expected_ids, all_ids


@pytest.mark.parametrize(
    "paginated",
    [pytest.param(False, id="plain_list"), pytest.param(True, id="paginated")],
)
def test_query_without_matches(base_url, query_bookings, paginated):

    params = query_bookings["name_params"].copy()

    params["lastname"] += "_missing"

    if paginated:
        params.update({"page": 1, "page_size": 2})

    response = requests.get(f"{base_url}/booking", params=params, timeout=5)

    assert response.status_code == 200, response.text

    data = response.json()

    if paginated:

        assert data == {"total": 0, "page": 1, "page_size": 2, "bookings": []}, data
    else:

        assert data == [], data


@pytest.mark.parametrize(
    "invalid_params, expected_error",
    [
        pytest.param(
            {"page": 0},
            "page must be >= 1 and page_size must be between 1 and 100",
            id="page_zero",
        ),
        pytest.param(
            {"page": "abc"},
            "Query parameter must be an integer: page",
            id="page_wrong_type",
        ),
        pytest.param(
            {"page_size": 101},
            "page must be >= 1 and page_size must be between 1 and 100",
            id="page_size_too_large",
        ),
    ],
)
def test_invalid_pagination_parameters(base_url, query_bookings, invalid_params, expected_error):

    params = query_bookings["name_params"].copy()

    params.update(invalid_params)

    response = requests.get(f"{base_url}/booking", params=params, timeout=5)

    assert response.status_code == 400, response.text

    assert response.json() == {"error": expected_error}, response.text
