import json
import os
import uuid
import mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# --- Settings ---
DB_FILE = "db.json"
STATIC_FOLDER = "public"
HOST = "127.0.0.1"
PORT = 5000
PER_PAGE_DEFAULT = 10

# --- Database Operations ---
def load_db():
    """Load the db.json file."""
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Warning: '{DB_FILE}' not found or invalid. Starting with an empty DB.")
        return {}

def save_db(db):
    """Write to the db.json file."""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error: Failed to save DB: {e}")

# --- API Logic Handler ---
class APIHandler:
    def __init__(self, path, method, body, db):
        parsed_path = urlparse(path)
        self.path = parsed_path.path
        self.args = parse_qs(parsed_path.query)
        self.method = method
        self.body = body
        self.db = db
        self.resource = None
        self.item_id = None

    def process_request(self):
        """Main entry point to handle the API request."""
        parts = self.path.strip("/").split("/")
        self.resource = parts[0] if parts else ""
        self.item_id = parts[1] if len(parts) > 1 else None

        if not self.resource:
            if self.method == "GET":
                return 200, list(self.db.keys()), {}
            else:
                return 404, {"error": "Not Found"}, {}

        if self.resource not in self.db:
            if self.method == "POST":
                self.db[self.resource] = []
            else:
                return 404, {"error": f"Resource '{self.resource}' not found."}, {}

        if self.method in ["PUT", "PATCH"]:
            handler = self.handle_put_patch
        else:
            handler = getattr(self, f"handle_{self.method.lower()}", self.handle_not_allowed)
        return handler()

    def handle_get(self):
        if self.item_id:
            item = self._get_item_by_id(self.item_id)
            if "_expand" in self.args:
                item = self._expand_item(item, self.args.get("_expand", []))
            if "_embed" in self.args:
                item = self._embed_related(item, self.args.get("_embed", []))
            return 200, item, {}
        else:
            items = list(self.db.get(self.resource, []))
            items = self._apply_filters_and_search(items)
            items = self._apply_sorting(items)
            total_count = len(items)
            items = self._apply_pagination(items)
            if "_embed" in self.args:
                items = self._apply_embedding(items)
            
            headers = {"X-Total-Count": str(total_count)}
            return 200, items, headers

    def handle_post(self):
        if not isinstance(self.body, dict):
            raise ValueError("Request body must be a JSON object.")
        if "id" not in self.body:
            self.body["id"] = uuid.uuid4().hex
        self.db[self.resource].append(self.body)
        return 201, self.body, {}

    def handle_put_patch(self):
        if not self.item_id:
            raise ValueError("An ID is required for updates.")
        if not isinstance(self.body, dict):
            raise ValueError("Request body must be a JSON object.")

        items = self.db.get(self.resource, [])
        item_index = next((i for i, item in enumerate(items) if str(item.get("id")) == str(self.item_id)), -1)
        if item_index == -1:
            raise FileNotFoundError(f"Item with ID '{self.item_id}' not found.")
        
        if self.method == "PUT":
            self.body["id"] = items[item_index]["id"]
            self.db[self.resource][item_index] = self.body
        else:  # PATCH
            self.db[self.resource][item_index].update(self.body)
        
        return 200, self.db[self.resource][item_index], {}

    def handle_delete(self):
        if not self.item_id:
            raise ValueError("An ID is required for deletion.")
        self._get_item_by_id(self.item_id) # Ensures item exists
        
        items = self.db.get(self.resource, [])
        self.db[self.resource] = [i for i in items if str(i.get("id")) != str(self.item_id)]

        if "_dependent" in self.args:
            dependent_resources = self.args.get("_dependent", [])
            foreign_key = f"{self.resource[:-1]}Id"
            for dep_res in dependent_resources:
                if dep_res in self.db:
                    self.db[dep_res] = [i for i in self.db[dep_res] if str(i.get(foreign_key)) != str(self.item_id)]
        return 200, {}, {}

    def handle_not_allowed(self):
        return 405, {"error": "Method Not Allowed"}, {}

    def _get_item_by_id(self, item_id):
        items = self.db.get(self.resource, [])
        item = next((i for i in items if str(i.get("id")) == str(item_id)), None)
        if item is None:
            raise FileNotFoundError(f"Item with ID '{item_id}' not found.")
        return item

    def _apply_filters_and_search(self, items):
        if "_q" in self.args:
            query = self.args["_q"][0].lower()
            items = [i for i in items if any(query in str(v).lower() for v in i.values())]

        for key, values in self.args.items():
            if key.startswith("_"):
                continue
            value = values[0]
            op = "eq"
            field = key
            if key.endswith(("_ne", "_lt", "_lte", "_gt", "_gte")):
                field, op = key.rsplit("_", 1)
            items = [i for i in items if self._filter_item(i, field, value, op)]
        return items

    def _apply_sorting(self, items):
        if "_sort" in self.args:
            sort_keys = self.args["_sort"][0].split(",")
            for key in reversed(sort_keys):
                reverse = key.startswith("-")
                key = key.lstrip("-")
                items.sort(key=lambda x: self._sorting_key(x, key), reverse=reverse)
        return items

    def _apply_pagination(self, items):
        if "_page" in self.args:
            page = int(self.args.get("_page", [1])[0])
            per_page = int(self.args.get("_per_page", [PER_PAGE_DEFAULT])[0])
            start = (page - 1) * per_page
            end = start + per_page
            return items[start:end]
        elif "_start" in self.args:
            start = int(self.args["_start"][0])
            if "_end" in self.args:
                end = int(self.args["_end"][0])
                return items[start:end]
            elif "_limit" in self.args:
                limit = int(self.args["_limit"][0])
                return items[start : start + limit]
        return items

    def _apply_embedding(self, items):
        embed_resources = self.args.get("_embed", [])
        return [self._embed_related(item, embed_resources) for item in items]

    def _filter_item(self, item, field, value, op):
        item_value = self._get_nested(item, field)
        if item_value is None:
            return False
        try:
            num_item_value, num_value = float(item_value), float(value)
            item_value, value = num_item_value, num_value
        except (ValueError, TypeError):
            item_value, value = str(item_value), str(value)
        
        ops = {
            "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
            "lt": lambda a, b: a < b, "lte": lambda a, b: a <= b,
            "gt": lambda a, b: a > b, "gte": lambda a, b: a >= b,
        }
        return ops[op](item_value, value)

    def _embed_related(self, item, embed_resources):
        item_id = item.get("id")
        if not item_id:
            return item
        for res_to_embed in embed_resources:
            if res_to_embed in self.db:
                foreign_key = f"{self.resource[:-1]}Id"
                related_items = [
                    rel_item for rel_item in self.db[res_to_embed]
                    if str(rel_item.get(foreign_key)) == str(item_id)
                ]
                item[res_to_embed] = related_items
        return item

    def _expand_item(self, item, expand_resources):
        for res_to_expand in expand_resources:
            foreign_key = f"{res_to_expand}Id"
            parent_id = item.get(foreign_key)
            resource_key = res_to_expand
            if resource_key not in self.db:
                resource_key = f"{res_to_expand}s"
            
            if parent_id and resource_key in self.db:
                parent_item = next(
                    (p for p in self.db[resource_key] if str(p.get("id")) == str(parent_id)),
                    None,
                )
                if parent_item:
                    item[res_to_expand] = parent_item
        return item

    def _get_nested(self, data, key):
        keys = key.split(".")
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k)
            else:
                return None
        return data

    def _sorting_key(self, item, key):
        value = self._get_nested(item, key)
        if value is None:
            return (-1, None)
        try:
            return (0, float(value))
        except (ValueError, TypeError):
            return (1, str(value))

# --- Main Server Handler ---
class JSONServer(BaseHTTPRequestHandler):
    def _send_response(self, status_code, data=None, headers=None):
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        if data is not None:
            self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))

    def _get_request_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def _handle_request(self, method):
        # Static file serving
        if method == "GET" and os.path.exists(STATIC_FOLDER):
            static_path = os.path.join(STATIC_FOLDER, self.path.lstrip('/'))
            if os.path.isfile(static_path):
                self.send_response(200)
                mimetype, _ = mimetypes.guess_type(static_path)
                self.send_header("Content-type", mimetype or "application/octet-stream")
                self.end_headers()
                with open(static_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        # API logic
        db = load_db()
        body = self._get_request_body() if method in ["POST", "PUT", "PATCH"] else None
        
        try:
            handler = APIHandler(self.path, method, body, db)
            status_code, data, headers = handler.process_request()
        except (ValueError, FileNotFoundError) as e:
            status_code, data, headers = (400 if isinstance(e, ValueError) else 404), {"error": str(e)}, {}

        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            save_db(db)

        self._send_response(status_code, data, headers)

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def do_PUT(self):
        self._handle_request("PUT")

    def do_PATCH(self):
        self._handle_request("PATCH")

    def do_DELETE(self):
        self._handle_request("DELETE")

    def do_OPTIONS(self):
        self._handle_request("OPTIONS")

# --- Server Startup ---
def main():
    """Start the server."""
    server_address = (HOST, PORT)
    httpd = HTTPServer(server_address, JSONServer)
    print(f"Python JSON Server is running on http://{HOST}:{PORT}")
    print(f"Watching DB file: {DB_FILE}")
    print(f"Serving static files from: {STATIC_FOLDER}")
    print("Press CTRL+C to stop")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
