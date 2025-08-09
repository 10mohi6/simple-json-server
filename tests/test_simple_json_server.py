import json
import os
import shutil
import threading
import requests
import pytest
from http.server import HTTPServer
from socketserver import ThreadingMixIn
import tempfile

from simple_json_server.simple_json_server import JSONServer

# --- Test Setup and Fixtures ---

class ReusableThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """A server that allows address reuse and handles requests in threads."""
    allow_reuse_address = True

@pytest.fixture(scope="function")
def running_server():
    """Fixture to run the HTTP server on a free ephemeral port with a temporary file system."""
    # Create a temporary directory for all test artifacts
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "db.json")
    static_path = os.path.join(temp_dir, "public")
    os.makedirs(static_path)

    # Point the server to use the temporary folders
    JSONServer.directory = static_path

    # Setup temporary environment
    setup_test_environment(db_path, static_path)

    # Bind to port 0 to let the OS pick a free port
    server_address = ("127.0.0.1", 0)
    
    def handler(*args, **kwargs):
        return JSONServer(*args, db_path=db_path, **kwargs)

    httpd = ReusableThreadingHTTPServer(server_address, handler)
    
    host, port = httpd.server_address
    server_url = f"http://{host}:{port}"

    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    yield server_url  # Provide the server URL to the test

    httpd.shutdown()
    httpd.server_close()
    # Clean up the entire temporary directory
    shutil.rmtree(temp_dir)

def setup_test_environment(db_path, static_path):
    """Creates a temporary database and static files for testing."""
    test_db_data = {
        "posts": [
            {"id": "1", "title": "json-server", "views": 100, "authorId": "1"},
            {"id": "2", "title": "python-flask", "views": 200, "authorId": "1"},
            {"id": "3", "title": "testing", "views": 50, "authorId": "2"},
        ],
        "authors": [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ],
        "comments": [
            {"id": "1", "text": "Great post!", "postId": "1"},
            {"id": "2", "text": "Very informative", "postId": "1"},
        ],
    }
    with open(db_path, "w") as f:
        json.dump(test_db_data, f, indent=2)

    with open(os.path.join(static_path, "index.html"), "w") as f:
        f.write("<h1>Hello</h1>")
    with open(os.path.join(static_path, "admin.html"), "w") as f:
        f.write("<title>JSON Server Admin</title>")

# --- Test Cases (no changes needed below this line) ---

def test_get_all_resources(running_server):
    response = requests.get(running_server)
    assert response.status_code == 200
    assert response.json() == ["posts", "authors", "comments"]

def test_get_all_posts(running_server):
    response = requests.get(f"{running_server}/posts")
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert response.headers["X-Total-Count"] == "3"

def test_get_single_post(running_server):
    response = requests.get(f"{running_server}/posts/1")
    assert response.status_code == 200
    assert response.json()["title"] == "json-server"

def test_get_item_not_found(running_server):
    response = requests.get(f"{running_server}/posts/999")
    assert response.status_code == 404

def test_create_post(running_server):
    new_post = {"title": "new-post", "views": 10}
    response = requests.post(f"{running_server}/posts", json=new_post)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "new-post"
    assert "id" in data
    get_response = requests.get(f"{running_server}/posts")
    assert len(get_response.json()) == 4

def test_update_post_put(running_server):
    update_data = {"title": "updated-title", "views": 500}
    response = requests.put(f"{running_server}/posts/1", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "updated-title"
    assert data["id"] == "1"

def test_update_post_patch(running_server):
    patch_data = {"views": 101}
    response = requests.patch(f"{running_server}/posts/1", json=patch_data)
    assert response.status_code == 200
    assert response.json()["views"] == 101

def test_delete_post(running_server):
    response = requests.delete(f"{running_server}/posts/1")
    assert response.status_code == 200
    get_response = requests.get(f"{running_server}/posts/1")
    assert get_response.status_code == 404

# --- Querying Tests ---

def test_filter_posts(running_server):
    response = requests.get(f"{running_server}/posts?views_gte=100")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_sort_posts(running_server):
    response = requests.get(f"{running_server}/posts?_sort=-views")
    assert response.status_code == 200
    assert response.json()[0]["views"] == 200

def test_paginate_posts(running_server):
    response = requests.get(f"{running_server}/posts?_sort=id&_page=2&_per_page=1")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_full_text_search(running_server):
    response = requests.get(f"{running_server}/posts?_q=python")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_expand_relationship(running_server):
    response = requests.get(f"{running_server}/posts/1?_expand=author")
    assert response.status_code == 200
    assert "author" in response.json()

def test_embed_related(running_server):
    response = requests.get(f"{running_server}/authors/1?_embed=posts")
    assert response.status_code == 200
    assert len(response.json()["posts"]) == 2

# --- Edge Case and Error Handling Tests ---

def test_invalid_json_body(running_server):
    headers = {"Content-Type": "application/json"}
    response = requests.post(f"{running_server}/posts", data="{{\"title\":,}}", headers=headers)
    assert response.status_code == 400

def test_dependent_deletion(running_server):
    requests.delete(f"{running_server}/posts/1?_dependent=comments")
    response = requests.get(f"{running_server}/comments?postId=1")
    assert len(response.json()) == 0

# --- Admin UI and DB Endpoint Tests ---

def test_serve_admin_page(running_server):
    response = requests.get(f"{running_server}/admin.html")
    assert response.status_code == 200
    assert "<title>JSON Server Admin</title>" in response.text

def test_get_raw_db(running_server):
    response = requests.get(f"{running_server}/_db")
    assert response.status_code == 200
    assert "posts" in response.json()

def test_set_raw_db(running_server):
    new_db = {"users": [{"id": 1}]}
    response = requests.put(f"{running_server}/_db", json=new_db)
    assert response.status_code == 200
    assert requests.get(f"{running_server}/_db").json() == new_db
