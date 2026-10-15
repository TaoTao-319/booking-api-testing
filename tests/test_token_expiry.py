import importlib.util

import threading

import time

from copy import deepcopy

from pathlib import Path


import pytest

import requests


EXPECTED_EXPIRED_STATUS = 403


WAIT_SECONDS = 3


@pytest.fixture
def short_lived_service():

    server_path = Path(__file__).resolve().parents[1] / "local-api" / "server.py"

    spec = importlib.util.spec_from_file_location("expiry_exercise_server", server_path)

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    try:
        server = module.BookingServer(("127.0.0.1", 0), token_ttl=2)

    except OSError as error:

        pytest.fail(f"短有效期服务无法启动：{error}")

    worker = threading.Thread(target=server.serve_forever, daemon=True)

    worker.start()

    try:

        yield f"http://127.0.0.1:{server.server_port}"
    finally:

        server.shutdown()

        server.server_close()

        worker.join(timeout=5)


def test_expired_token_cannot_update_booking(short_lived_service, auth_booking_factory):

    base_url = short_lived_service

    with auth_booking_factory(base_url) as booking:

        dedicated_token = booking["token"]


        expired_cookies = {"token": dedicated_token}


        updated_data = deepcopy(booking["data"])

        assert updated_data["totalprice"] == 200, updated_data

        updated_data["totalprice"] = 300


        time.sleep(WAIT_SECONDS)

        response = requests.put(
            f"{base_url}/booking/{booking['id']}",
            json=updated_data,
            cookies=expired_cookies,
            timeout=5,
        )

        assert response.status_code == EXPECTED_EXPIRED_STATUS, response.text

        assert response.json() == {"error": "Token has expired"}, response.text


        query_response = requests.get(
            f"{base_url}/booking/{booking['id']}", timeout=5
        )

        assert query_response.status_code == 200, query_response.text

        assert query_response.json() == booking["data"], query_response.text

