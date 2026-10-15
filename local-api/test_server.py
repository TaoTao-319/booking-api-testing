from copy import deepcopy
from http.client import HTTPConnection
import json
import threading
import time
import unittest

from server import BookingServer


SAMPLE = {
    "firstname": "Alex", "lastname": "Learner", "totalprice": 200,
    "depositpaid": True,
    "bookingdates": {"checkin": "2026-11-01", "checkout": "2026-11-03"},
    "additionalneeds": "Breakfast",
}


class ServerChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = BookingServer(("127.0.0.1", 0), token_ttl=3600)

        cls.server.RequestHandlerClass.log_message = lambda *args: None
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=5)

    def setUp(self):
        self.server.bookings.clear()
        self.server.tokens.clear()
        self.server.next_id = 1
        self.server.clock = time.monotonic
        self.token = self.request("POST", "/auth", {"username": "admin", "password": "password123"})[1]["token"]
        self.booking_id = self.create()["bookingid"]
        self.path = f"/booking/{self.booking_id}"

    def request(self, method, path, data=None, token=None, raw=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {}
        body = raw
        if data is not None:
            body = json.dumps(data).encode("utf-8")
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["Cookie"] = "token=" + token
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            text = response.read()
            return response.status, json.loads(text) if text else None, dict(response.getheaders())
        finally:
            connection.close()

    def create(self, **changes):
        data = deepcopy(SAMPLE)
        data.update(changes)
        status, result, _ = self.request("POST", "/booking", data)
        self.assertEqual(status, 200)
        return result

    def assert_original(self):
        status, data, _ = self.request("GET", self.path)
        self.assertEqual(status, 200)
        self.assertEqual(data, SAMPLE)

    def test_health(self):
        self.assertEqual(self.request("GET", "/ping")[:2], (200, {"status": "ok"}))

    def test_auth(self):
        status, data, _ = self.request("POST", "/auth", {"username": "admin", "password": "password123"})
        self.assertEqual(status, 200)
        self.assertIsInstance(data["token"], str)
        self.assertNotEqual(data["token"], self.token)
        self.assertEqual(data["expires_in"], 3600)

    def test_bad_credentials(self):
        for data in ({"username": "admin", "password": "wrong_password"}, {}, [], {"username": "admin", "password": 123}):
            with self.subTest(data=data):
                self.assertEqual(self.request("POST", "/auth", data)[:2], (401, {"error": "Bad credentials"}))

    def test_list_legacy_shape(self):
        self.assertEqual(self.request("GET", "/booking")[:2], (200, [{"bookingid": self.booking_id}]))

    def test_create_and_get(self):
        result = self.create(firstname="Other")
        self.assertIs(type(result["bookingid"]), int)
        self.assertGreater(result["bookingid"], self.booking_id)
        self.assertEqual(result["booking"]["firstname"], "Other")
        self.assertEqual(self.request("GET", f'/booking/{result["bookingid"]}')[1], result["booking"])

    def test_name_filters(self):
        self.create(firstname="Other")
        for query, expected in (("firstname=Alex&lastname=Learner", [{"bookingid": self.booking_id}]), ("firstname=alex", []), ("firstname=Alex&lastname=Other", [])):
            with self.subTest(query=query):
                self.assertEqual(self.request("GET", "/booking?" + query)[:2], (200, expected))

    def test_put_replaces_whole_booking(self):
        data = deepcopy(SAMPLE)
        data["totalprice"] = 300
        del data["additionalneeds"]
        self.assertEqual(self.request("PUT", self.path, data, self.token)[:2], (200, data))
        self.assertEqual(self.request("GET", self.path)[1], data)

    def test_delete_then_missing(self):
        self.assertEqual(self.request("DELETE", self.path, token=self.token)[:2], (201, {"message": "Booking deleted"}))
        self.assertEqual(self.request("GET", self.path)[0], 404)

    def test_legacy_validation_messages(self):
        cases = []
        data = deepcopy(SAMPLE)
        del data["firstname"]
        cases.append((data, "Missing field: firstname"))
        data = deepcopy(SAMPLE)
        del data["bookingdates"]["checkout"]
        cases.append((data, "Missing or invalid bookingdates.checkout"))
        for field, value in (("totalprice", "200"), ("depositpaid", "true")):
            data = deepcopy(SAMPLE)
            data[field] = value
            cases.append((data, "Incorrect type: " + field))
        for data, error in cases:
            with self.subTest(error=error):
                self.assertEqual(self.request("POST", "/booking", data)[:2], (400, {"error": error}))
        self.assertEqual(len(self.server.bookings), 1)

    def test_invalid_json(self):
        for method, path, token in (("POST", "/booking", None), ("PUT", self.path, self.token), ("PATCH", self.path, self.token), ("POST", "/auth", None)):
            with self.subTest(method=method, path=path):
                self.assertEqual(self.request(method, path, token=token, raw=b'{"firstname": "Alex",}')[:2], (400, {"error": "Invalid JSON body"}))
        self.assert_original()

    def test_non_object_body(self):
        for body in ([], "hello", 123, True):
            for method, path, token in (("POST", "/booking", None), ("PUT", self.path, self.token), ("PATCH", self.path, self.token)):
                with self.subTest(body=body, method=method):
                    self.assertEqual(self.request(method, path, body, token)[:2], (400, {"error": "Body must be a JSON object"}))
        self.assert_original()

    def test_unauthorized_writes_do_not_change_data(self):
        for method in ("PUT", "PATCH", "DELETE"):
            for token in (None, "invalid_token"):
                with self.subTest(method=method, token=token):
                    body = {**SAMPLE, "totalprice": 300} if method == "PUT" else {"totalprice": 300} if method == "PATCH" else None
                    self.assertEqual(self.request(method, self.path, body, token)[:2], (403, {"error": "A valid token cookie is required"}))
                    self.assert_original()

    def test_missing_resource_all_methods(self):
        self.request("DELETE", self.path, token=self.token)
        for method in ("GET", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                body = SAMPLE if method == "PUT" else {"totalprice": 300} if method == "PATCH" else None
                self.assertEqual(self.request(method, self.path, body, self.token)[0], 404)

    def test_auth_checked_before_existence(self):
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self.request(method, "/booking/99999", SAMPLE)[0], 403)

    def test_patch_scalar_and_false_zero(self):
        body = {"totalprice": 0, "depositpaid": False, "additionalneeds": ""}
        expected = {**SAMPLE, **body}
        self.assertEqual(self.request("PATCH", self.path, body, self.token)[:2], (200, expected))
        self.assertEqual(self.request("GET", self.path)[1], expected)

    def test_patch_nested_preserves_checkin(self):
        expected = deepcopy(SAMPLE)
        expected["bookingdates"]["checkout"] = "2026-11-05"
        self.assertEqual(self.request("PATCH", self.path, {"bookingdates": {"checkout": "2026-11-05"}}, self.token)[:2], (200, expected))
        self.assertEqual(self.request("GET", self.path)[1], expected)

    def test_patch_repeated_same_data(self):
        body = {"totalprice": 300}
        first = self.request("PATCH", self.path, body, self.token)
        second = self.request("PATCH", self.path, body, self.token)
        self.assertEqual(first[:2], second[:2])

    def test_empty_patch_rejected(self):
        for body, error in (({}, "Patch body must not be empty"), ({"bookingdates": {}}, "bookingdates patch must not be empty")):
            with self.subTest(body=body):
                self.assertEqual(self.request("PATCH", self.path, body, self.token)[:2], (400, {"error": error}))
        self.assert_original()

    def test_unknown_fields_rejected(self):
        for body in ({"totlprice": 300}, {"bookingdates": {"checkuot": "2026-11-05"}}, {"bookingid": 99}):
            with self.subTest(body=body):
                self.assertEqual(self.request("PATCH", self.path, body, self.token)[0], 400)
        self.assertEqual(self.request("POST", "/booking", {**SAMPLE, "other": 1})[0], 400)
        self.assertEqual(self.request("PUT", self.path, {**SAMPLE, "other": 1}, self.token)[0], 400)
        self.assert_original()

    def test_strict_types_and_blanks(self):
        for body in ({"totalprice": True}, {"totalprice": 3.5}, {"totalprice": "300"}, {"totalprice": -1}, {"depositpaid": 1}, {"firstname": "  "}, {"lastname": ""}, {"additionalneeds": None}, {"bookingdates": []}):
            with self.subTest(body=body):
                self.assertEqual(self.request("PATCH", self.path, body, self.token)[0], 400)
                self.assertEqual(self.request("POST", "/booking", {**SAMPLE, **body})[0], 400)
                self.assertEqual(self.request("PUT", self.path, {**SAMPLE, **body}, self.token)[0], 400)
        self.assert_original()

    def test_invalid_dates(self):
        for value in ("2026-02-30", "20261105", "2026-1-5", "nonsense", None):
            with self.subTest(value=value):
                self.assertEqual(self.request("PATCH", self.path, {"bookingdates": {"checkout": value}}, self.token)[0], 400)
        self.assert_original()

    def test_patch_atomic_on_date_conflict(self):
        for checkout in ("2026-11-01", "2026-10-31"):
            with self.subTest(checkout=checkout):
                body = {"totalprice": 999, "bookingdates": {"checkout": checkout}}
                self.assertEqual(self.request("PATCH", self.path, body, self.token)[:2], (400, {"error": "checkout must be after checkin"}))
                self.assert_original()

    def test_full_write_date_conflict(self):
        body = deepcopy(SAMPLE)
        body["bookingdates"]["checkin"] = "2026-11-04"
        for method, path, token in (("POST", "/booking", None), ("PUT", self.path, self.token)):
            with self.subTest(method=method):
                self.assertEqual(self.request(method, path, body, token)[0], 400)
        self.assert_original()

    def test_combined_filters_and_inclusive_boundaries(self):
        self.create(totalprice=300, depositpaid=False)
        self.create(firstname="Other", totalprice=200)
        self.assertEqual(self.request("GET", "/booking?firstname=Alex&depositpaid=true&min_price=200&max_price=200")[1], [{"bookingid": self.booking_id}])
        self.assertEqual(self.request("GET", "/booking?firstname=Alex&depositpaid=false&min_price=250")[1], [{"bookingid": 2}])

    def test_date_filters(self):
        self.assertEqual(self.request("GET", "/booking?checkin=2026-11-01&checkout=2026-11-03")[1], [{"bookingid": self.booking_id}])
        self.assertEqual(self.request("GET", "/booking?checkin=2026-11-02")[1], [])

    def test_pagination_order_and_no_overlap(self):
        for price in (100, 300, 400, 500):
            self.create(totalprice=price)
        pages = [self.request("GET", f"/booking?page={page}&page_size=2")[1] for page in (1, 2, 3, 4)]
        self.assertEqual([data["bookings"] for data in pages], [[{"bookingid": 1}, {"bookingid": 2}], [{"bookingid": 3}, {"bookingid": 4}], [{"bookingid": 5}], []])
        self.assertTrue(all(data["total"] == 5 for data in pages))
        self.assertEqual([data["page"] for data in pages], [1, 2, 3, 4])

    def test_pagination_defaults_and_filtered_total(self):
        self.create(firstname="Other")
        data = self.request("GET", "/booking?firstname=Alex&page_size=1")[1]
        self.assertEqual(data, {"total": 1, "page": 1, "page_size": 1, "bookings": [{"bookingid": 1}]})
        self.assertEqual(self.request("GET", "/booking?page=1")[1]["page_size"], 10)
        data = self.request("GET", "/booking?firstname=Missing&page=1")[1]
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["bookings"], [])

    def test_invalid_queries(self):
        for query in ("page=0", "page=-1", "page=abc", "page_size=0", "page_size=101", "page_size=1.5", "min_price=-1", "min_price=301&max_price=300", "depositpaid=1", "unknown=1", "page=1&page=2", "firstname=", "page=", "checkout=2026-02-30"):
            with self.subTest(query=query):
                status, body, _ = self.request("GET", "/booking?" + query)
                self.assertEqual(status, 400)
                self.assertIsInstance(body["error"], str)

    def test_logout_invalidates_only_own_token(self):
        other_token = self.request("POST", "/auth", {"username": "admin", "password": "password123"})[1]["token"]
        self.assertEqual(self.request("DELETE", "/auth", token=self.token)[:2], (200, {"message": "Logged out"}))
        self.assertEqual(self.request("PATCH", self.path, {"totalprice": 300}, self.token)[0], 403)
        self.assert_original()
        self.assertEqual(self.request("PATCH", self.path, {"totalprice": 300}, other_token)[0], 200)

    def test_logout_requires_auth(self):
        for token in (None, "invalid_token"):
            with self.subTest(token=token):
                self.assertEqual(self.request("DELETE", "/auth", token=token)[0], 403)

    def test_expiry_rejects_all_writes(self):
        now = [100.0]
        self.server.clock = lambda: now[0]
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                token = self.request("POST", "/auth", {"username": "admin", "password": "password123"})[1]["token"]
                now[0] += 3600
                body = SAMPLE if method == "PUT" else {"totalprice": 300} if method == "PATCH" else None
                self.assertEqual(self.request(method, self.path, body, token)[:2], (403, {"error": "Token has expired"}))
                self.assert_original()
                self.assertEqual(self.request(method, self.path, body, token)[0], 403)

    def test_unknown_endpoint_and_method(self):
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self.request(method, "/missing")[0], 404)
        status, body, headers = self.request("PATCH", "/booking", {"totalprice": 300}, self.token)
        self.assertEqual(status, 405)
        self.assertEqual(body, {"error": "Method not allowed"})
        self.assertEqual(headers["Allow"], "GET, POST")
        self.assertEqual(self.request("HEAD", "/ping")[0], 405)
        self.assertEqual(self.request("OPTIONS", self.path)[0], 405)

    def test_json_content_type_and_unicode(self):
        result = self.create(firstname="张", lastname="学习")
        status, data, headers = self.request("GET", f'/booking/{result["bookingid"]}')
        self.assertEqual(status, 200)
        self.assertEqual(data["firstname"], "张")
        self.assertIn("application/json", headers["Content-Type"])

    def test_nonstandard_json_constants_rejected(self):
        for constant in (b"NaN", b"Infinity", b"-Infinity"):
            with self.subTest(constant=constant):
                body = b'{"totalprice":' + constant + b'}'
                self.assertEqual(self.request("PATCH", self.path, token=self.token, raw=body)[0], 400)
        self.assert_original()


if __name__ == "__main__":
    unittest.main(verbosity=2)
