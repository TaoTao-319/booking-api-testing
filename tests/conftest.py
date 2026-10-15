import json
import os

from copy import deepcopy

from contextlib import contextmanager

from pathlib import Path

from uuid import uuid4


import pytest

import requests


@pytest.fixture
def base_url():

    return os.environ.get("BOOKING_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture
def token(base_url):

    response = requests.post(
        f"{base_url}/auth",
        json={"username": "admin", "password": "password123"},
        timeout=5,
    )

    assert response.status_code == 200, response.text


    value = response.json()["token"]

    assert isinstance(value, str) and value, "登录响应必须包含非空字符串 token"


    try:

        yield value
    finally:

        response = requests.delete(
            f"{base_url}/auth",
            cookies={"token": value},
            timeout=5,
        )

        assert response.status_code == 200, f"注销 token 失败：{response.text}"

        assert response.json() == {"message": "Logged out"}, response.text


@pytest.fixture
def booking(base_url, token):

    template_path = Path(__file__).resolve().parent / "data" / "booking.json"

    payload = json.loads(template_path.read_text(encoding="utf-8"))

    payload["lastname"] = f"{payload['lastname']}_{uuid4().hex}"

    response = requests.post(
        f"{base_url}/booking",
        json=payload,
        timeout=5,
    )

    assert response.status_code == 200, response.text


    booking_id = response.json()["bookingid"]

    assert type(booking_id) is int and booking_id > 0, response.text


    try:

        yield {
            "id": booking_id,
            "data": deepcopy(payload),
            "response": response,
        }
    finally:

        cleanup_response = requests.delete(
            f"{base_url}/booking/{booking_id}",
            cookies={"token": token},
            timeout=5,
        )

        assert cleanup_response.status_code in (201, 404), (
            f"清理预约 {booking_id} 失败："
            f"{cleanup_response.status_code} {cleanup_response.text}"
        )

        if cleanup_response.status_code == 201:

            assert cleanup_response.json() == {"message": "Booking deleted"}
        else:

            assert cleanup_response.json() == {"error": "Booking not found"}


@pytest.fixture
def booking_factory(base_url, token):

    created_ids = []

    def create(**changes):

        template_path = Path(__file__).resolve().parent / "data" / "booking.json"

        payload = json.loads(template_path.read_text(encoding="utf-8"))

        payload["lastname"] = f"{payload['lastname']}_{uuid4().hex}"

        payload.update(deepcopy(changes))

        response = requests.post(f"{base_url}/booking", json=payload, timeout=5)

        assert response.status_code == 200, response.text

        booking_id = response.json()["bookingid"]

        assert type(booking_id) is int and booking_id > 0, response.text

        created_ids.append(booking_id)

        assert response.json()["booking"] == payload, response.text

        return {"id": booking_id, "data": deepcopy(payload), "response": response}

    try:

        yield create
    finally:

        cleanup_errors = []

        for booking_id in reversed(created_ids):
            try:

                response = requests.delete(
                    f"{base_url}/booking/{booking_id}",
                    cookies={"token": token},
                    timeout=5,
                )

                assert response.status_code in (201, 404), response.text

                expected_body = (
                    {"message": "Booking deleted"}
                    if response.status_code == 201
                    else {"error": "Booking not found"}
                )

                assert response.json() == expected_body, response.text
            except (requests.RequestException, AssertionError) as error:

                cleanup_errors.append(f"预约 {booking_id} 清理失败：{error}")

        assert not cleanup_errors, "\n".join(cleanup_errors)


def _login_for_auth_test(service_url):

    response = requests.post(
        f"{service_url}/auth",
        json={"username": "admin", "password": "password123"},
        timeout=5,
    )

    assert response.status_code == 200, response.text

    value = response.json()["token"]

    assert isinstance(value, str) and value, response.text

    return value


@pytest.fixture
def auth_booking_factory():


    @contextmanager
    def create(service_url):

        dedicated_token = _login_for_auth_test(service_url)

        booking_id = None
        try:

            template_path = Path(__file__).resolve().parent / "data" / "booking.json"

            payload = json.loads(template_path.read_text(encoding="utf-8"))

            payload["lastname"] = f"{payload['lastname']}_Auth_{uuid4().hex}"

            response = requests.post(
                f"{service_url}/booking", json=payload, timeout=5
            )

            assert response.status_code == 200, response.text

            booking_id = response.json()["bookingid"]

            assert type(booking_id) is int and booking_id > 0, response.text

            yield {
                "id": booking_id,
                "data": deepcopy(payload),
                "token": dedicated_token,
            }
        finally:

            try:

                if booking_id is not None:

                    cleanup_token = _login_for_auth_test(service_url)
                    try:

                        response = requests.delete(
                            f"{service_url}/booking/{booking_id}",
                            cookies={"token": cleanup_token},
                            timeout=5,
                        )

                        assert response.status_code in (201, 404), response.text

                        expected_body = (
                            {"message": "Booking deleted"}
                            if response.status_code == 201
                            else {"error": "Booking not found"}
                        )

                        assert response.json() == expected_body, response.text
                    finally:

                        response = requests.delete(
                            f"{service_url}/auth",
                            cookies={"token": cleanup_token},
                            timeout=5,
                        )

                        assert response.status_code == 200, response.text

                        assert response.json() == {"message": "Logged out"}, response.text
            finally:

                response = requests.delete(
                    f"{service_url}/auth",
                    cookies={"token": dedicated_token},
                    timeout=5,
                )

                assert response.status_code in (200, 403), response.text
                if response.status_code == 200:

                    assert response.json() == {"message": "Logged out"}, response.text
                else:

                    assert response.json() in (
                        {"error": "A valid token cookie is required"},
                        {"error": "Token has expired"},
                    ), response.text


    return create
