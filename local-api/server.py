import argparse
from copy import deepcopy
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import secrets
import time
from urllib.parse import parse_qs, urlsplit


FIELD_TYPES = {
    "firstname": str, "lastname": str, "totalprice": int,
    "depositpaid": bool, "bookingdates": dict, "additionalneeds": str,
}
REQUIRED = ("firstname", "lastname", "totalprice", "depositpaid", "bookingdates")


def iso_date(value):
    if type(value) is not str:
        raise ValueError("Date must be a string")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Use YYYY-MM-DD")
    return parsed


def booking_error(data, partial=False):
    if type(data) is not dict:
        return "Body must be a JSON object"
    if partial and not data:
        return "Patch body must not be empty"
    unknown = set(data) - set(FIELD_TYPES)
    if unknown:
        return "Unknown field: " + sorted(unknown)[0]
    for name in REQUIRED:
        if not partial and name not in data:
            return "Missing field: " + name
    for name, value in data.items():
        if type(value) is not FIELD_TYPES[name]:
            return "Incorrect type: " + name
    for name in ("firstname", "lastname"):
        if name in data and not data[name].strip():
            return "Must not be blank: " + name
    if "totalprice" in data and data["totalprice"] < 0:
        return "totalprice must be greater than or equal to 0"
    if "bookingdates" in data:
        dates = data["bookingdates"]
        unknown_dates = set(dates) - {"checkin", "checkout"}
        if unknown_dates:
            return "Unknown field: bookingdates." + sorted(unknown_dates)[0]
        if partial and not dates:
            return "bookingdates patch must not be empty"
        for name in ("checkin", "checkout"):
            if not partial and type(dates.get(name)) is not str:
                return "Missing or invalid bookingdates." + name
            if name in dates:
                try:
                    iso_date(dates[name])
                except (ValueError, TypeError):
                    return "Invalid date: bookingdates." + name + " (use YYYY-MM-DD)"
        if "checkin" in dates and "checkout" in dates:
            if iso_date(dates["checkout"]) <= iso_date(dates["checkin"]):
                return "checkout must be after checkin"
    return None


class BookingServer(HTTPServer):
    def __init__(self, address, token_ttl=3600):
        super().__init__(address, BookingAPI)
        self.bookings = {}
        self.tokens = {}
        self.next_id = 1
        self.token_ttl = token_ttl
        self.clock = time.monotonic


class BookingAPI(BaseHTTPRequestHandler):
    def reply(self, status, data=None, allow=None):
        body = b"" if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        if data is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        if allow:
            self.send_header("Allow", allow)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        self.reply(405 if code == 501 else code,
                   {"error": "Method not allowed" if code == 501 else (message or "HTTP error")})

    def read_json(self):
        def reject_constant(value):
            raise ValueError("Invalid JSON constant: " + value)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 1_000_000:
                raise ValueError("Invalid body length")
            data = json.loads(self.rfile.read(length), parse_constant=reject_constant)
            return data, True
        except (ValueError, UnicodeDecodeError):
            self.reply(400, {"error": "Invalid JSON body"})
            return None, False

    def authorized(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            item = cookie.get("token")
            token = item.value if item else None
        except Exception:
            token = None
        expiry = self.server.tokens.get(token)
        if expiry is None:
            self.reply(403, {"error": "A valid token cookie is required"})
            return None
        if self.server.clock() >= expiry:
            self.server.tokens.pop(token, None)
            self.reply(403, {"error": "Token has expired"})
            return None
        return token

    def booking_id(self):
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "booking" and parts[1].isascii() and parts[1].isdigit():
            try:
                return int(parts[1])
            except ValueError:
                return None
        return None

    def unsupported(self):
        path = urlsplit(self.path).path
        allow = {"/ping": "GET", "/auth": "POST, DELETE", "/booking": "GET, POST"}.get(path)
        if allow is None and self.booking_id() is not None:
            allow = "GET, PUT, PATCH, DELETE"
        if allow:
            self.reply(405, {"error": "Method not allowed"}, allow=allow)
        else:
            self.reply(404, {"error": "Endpoint not found"})

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/ping":
            self.reply(200, {"status": "ok"})
        elif url.path == "/booking":
            self.list_bookings(url.query)
        elif self.booking_id() is not None:
            booking = self.server.bookings.get(self.booking_id())
            if booking is None:
                self.reply(404, {"error": "Booking or endpoint not found"})
            else:
                self.reply(200, booking)
        else:
            self.unsupported()

    def list_bookings(self, query):
        filters = parse_qs(query, keep_blank_values=True)
        allowed = {"firstname", "lastname", "depositpaid", "min_price", "max_price", "checkin", "checkout", "page", "page_size"}
        try:
            for key, values in filters.items():
                if key not in allowed:
                    raise ValueError("Unknown query parameter: " + key)
                if len(values) != 1 or not values[0].strip():
                    raise ValueError("Query parameter must have one non-empty value: " + key)
            numbers = {}
            for key in ("min_price", "max_price", "page", "page_size"):
                if key in filters:
                    value = filters[key][0]
                    if not value.isascii() or not value.isdigit():
                        raise ValueError("Query parameter must be an integer: " + key)
                    numbers[key] = int(value)
            if numbers.get("min_price", 0) > numbers.get("max_price", math.inf):
                raise ValueError("min_price must not exceed max_price")
            if "depositpaid" in filters and filters["depositpaid"][0] not in ("true", "false"):
                raise ValueError("depositpaid filter must be true or false")
            for key in ("checkin", "checkout"):
                if key in filters:
                    try:
                        iso_date(filters[key][0])
                    except (ValueError, TypeError):
                        raise ValueError("Invalid date filter: " + key + " (use YYYY-MM-DD)")
            paginated = "page" in filters or "page_size" in filters
            page = numbers.get("page", 1)
            page_size = numbers.get("page_size", 10)
            if page < 1 or not 1 <= page_size <= 100:
                raise ValueError("page must be >= 1 and page_size must be between 1 and 100")
        except ValueError as error:
            self.reply(400, {"error": str(error)})
            return
        matches = []
        for booking_id, booking in sorted(self.server.bookings.items()):
            if any(booking[key] != filters[key][0] for key in ("firstname", "lastname") if key in filters):
                continue
            if "depositpaid" in filters and booking["depositpaid"] != (filters["depositpaid"][0] == "true"):
                continue
            if not numbers.get("min_price", 0) <= booking["totalprice"] <= numbers.get("max_price", math.inf):
                continue
            if any(booking["bookingdates"][key] != filters[key][0] for key in ("checkin", "checkout") if key in filters):
                continue
            matches.append({"bookingid": booking_id})
        if paginated:
            start = (page - 1) * page_size
            self.reply(200, {"total": len(matches), "page": page, "page_size": page_size,
                             "bookings": matches[start:start + page_size]})
        else:
            self.reply(200, matches)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ("/auth", "/booking"):
            self.unsupported()
            return
        data, valid = self.read_json()
        if not valid:
            return
        if path == "/auth":
            if isinstance(data, dict) and data.get("username") == "admin" and data.get("password") == "password123":
                now = self.server.clock()
                self.server.tokens = {token: expiry for token, expiry in self.server.tokens.items() if expiry > now}
                token = secrets.token_hex(16)
                self.server.tokens[token] = now + self.server.token_ttl
                self.reply(200, {"token": token, "expires_in": self.server.token_ttl})
            else:
                self.reply(401, {"error": "Bad credentials"})
            return
        error = booking_error(data)
        if error:
            self.reply(400, {"error": error})
            return
        booking_id = self.server.next_id
        self.server.next_id += 1
        self.server.bookings[booking_id] = deepcopy(data)
        self.reply(200, {"bookingid": booking_id, "booking": data})

    def update_booking(self, partial):
        booking_id = self.booking_id()
        if booking_id is None:
            self.unsupported()
            return
        if not self.authorized():
            return
        if booking_id not in self.server.bookings:
            self.reply(404, {"error": "Booking not found"})
            return
        data, valid = self.read_json()
        if not valid:
            return
        error = booking_error(data, partial=partial)
        if error:
            self.reply(400, {"error": error})
            return
        if partial:
            candidate = deepcopy(self.server.bookings[booking_id])
            for key, value in data.items():
                if key == "bookingdates":
                    candidate[key].update(value)
                else:
                    candidate[key] = value
        else:
            candidate = deepcopy(data)
        error = booking_error(candidate)
        if error:
            self.reply(400, {"error": error})
            return

        self.server.bookings[booking_id] = candidate
        self.reply(200, candidate)

    def do_PUT(self):
        self.update_booking(partial=False)

    def do_PATCH(self):
        self.update_booking(partial=True)

    def do_DELETE(self):
        path = urlsplit(self.path).path
        if path == "/auth":
            token = self.authorized()
            if token:
                del self.server.tokens[token]
                self.reply(200, {"message": "Logged out"})
            return
        booking_id = self.booking_id()
        if booking_id is None:
            self.unsupported()
            return
        if not self.authorized():
            return
        if booking_id not in self.server.bookings:
            self.reply(404, {"error": "Booking not found"})
            return
        del self.server.bookings[booking_id]
        self.reply(201, {"message": "Booking deleted"})

    def do_HEAD(self):
        self.unsupported()

    def do_OPTIONS(self):
        self.unsupported()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token-ttl", type=int, default=3600, help="Token lifetime in seconds")
    args = parser.parse_args()
    if args.token_ttl < 1:
        parser.error("--token-ttl must be >= 1")
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    try:
        server = BookingServer((args.host, args.port), args.token_ttl)
    except OSError as error:
        parser.exit(1, f"Cannot start server: {error}. Try --port 8001 if the port is occupied.\n")
    print(f"Local booking API: http://{args.host}:{server.server_port}", flush=True)
    print(f"Demo credentials: admin / password123; token TTL: {args.token_ttl}s", flush=True)
    print("Keep this terminal open. Ctrl+C stops the server. Restart clears all data.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
