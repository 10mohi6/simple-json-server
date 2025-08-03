import json
import os
import shutil
import threading
import time
import requests
import pytest

from simple_json_server.simple_json_server import HTTPServer, JSONServer, HOST, PORT, DB_FILE, STATIC_FOLDER

# --- Test Setup and Fixtures ---

SERVER_URL = f"http://{HOST}:{PORT}"

@pytest.fixture(scope="function")
def test_server():
    """Fixture to run the HTTP server in a separate thread."""
    # Setup: create a temporary db and static folder
    setup_test_environment(DB_FILE, STATIC_FOLDER)

    server_address = (HOST, PORT)
    httpd = HTTPServer(server_address, JSONServer)
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Wait a moment for the server to start
    time.sleep(0.1)

    yield

    # Teardown: stop the server and clean up
    httpd.shutdown()
    httpd.server_close()
    teardown_test_environment(DB_FILE, STATIC_FOLDER)

def setup_test_environment(db_path, static_path):
    """Creates a temporary database and static folder for testing."""
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

    if not os.path.exists(static_path):
        os.makedirs(static_path)
    with open(os.path.join(static_path, "index.html"), "w") as f:
        f.write("<h1>Hello</h1>")

def teardown_test_environment(db_path, static_path):
    """Removes the temporary database and static folder."""
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists(static_path):
        shutil.rmtree(static_path)

# --- Test Cases ---

def test_get_all_resources(test_server):
    """GET / - Should return all resource keys."""
    response = requests.get(SERVER_URL)
    assert response.status_code == 200
    assert response.json() == ["posts", "authors", "comments"]

def test_get_all_posts(test_server):
    """GET /posts - Should return all items in a resource."""
    response = requests.get(f"{SERVER_URL}/posts")
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert response.headers["X-Total-Count"] == "3"

def test_get_single_post(test_server):
    """GET /posts/:id - Should return a single item."""
    response = requests.get(f"{SERVER_URL}/posts/1")
    assert response.status_code == 200
    assert response.json()["title"] == "json-server"

def test_get_item_not_found(test_server):
    """GET /posts/:id - Should return 404 if item not found."""
    response = requests.get(f"{SERVER_URL}/posts/999")
    assert response.status_code == 404

def test_create_post(test_server):
    """POST /posts - Should create a new item."""
    new_post = {"title": "new-post", "views": 10}
    response = requests.post(f"{SERVER_URL}/posts", json=new_post)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "new-post"
    assert "id" in data

    get_response = requests.get(f"{SERVER_URL}/posts")
    assert len(get_response.json()) == 4

def test_update_post_put(test_server):
    """PUT /posts/:id - Should replace an item."""
    update_data = {"title": "updated-title", "views": 500}
    response = requests.put(f"{SERVER_URL}/posts/1", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "updated-title"
    assert data["views"] == 500
    assert data["id"] == "1"
    assert "authorId" not in data

def test_update_post_patch(test_server):
    """PATCH /posts/:id - Should partially update an item."""
    patch_data = {"views": 101}
    response = requests.patch(f"{SERVER_URL}/posts/1", json=patch_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "json-server"
    assert data["views"] == 101

def test_delete_post(test_server):
    """DELETE /posts/:id - Should delete an item."""
    response = requests.delete(f"{SERVER_URL}/posts/1")
    assert response.status_code == 200
    assert response.json() == {}

    get_response = requests.get(f"{SERVER_URL}/posts/1")
    assert get_response.status_code == 404

# --- Querying Tests ---

def test_filter_posts(test_server):
    """GET /posts?views_gte=100 - Should filter results."""
    response = requests.get(f"{SERVER_URL}/posts?views_gte=100")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(item["views"] >= 100 for item in data)

def test_sort_posts(test_server):
    """GET /posts?_sort=-views - Should sort results."""
    response = requests.get(f"{SERVER_URL}/posts?_sort=-views")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["views"] == 200

def test_paginate_posts(test_server):
    """GET /posts?_page=2&_per_page=1 - Should paginate results."""
    response = requests.get(f"{SERVER_URL}/posts?_sort=id&_page=2&_per_page=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "2"

def test_full_text_search(test_server):
    """GET /posts?_q=python - Should perform a full-text search."""
    response = requests.get(f"{SERVER_URL}/posts?_q=python")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "python-flask"

def test_expand_relationship(test_server):
    """GET /posts/1?_expand=author - Should expand a parent resource."""
    response = requests.get(f"{SERVER_URL}/posts/1?_expand=author")
    assert response.status_code == 200
    data = response.json()
    assert "author" in data
    assert data["author"]["name"] == "Alice"

def test_embed_related(test_server):
    """GET /authors/1?_embed=posts - Should embed related children resources."""
    response = requests.get(f"{SERVER_URL}/authors/1?_embed=posts")
    assert response.status_code == 200
    data = response.json()
    assert "posts" in data
    assert len(data["posts"]) == 2

# --- Edge Case and Error Handling Tests ---

def test_invalid_json_body(test_server):
    """POST /posts with invalid JSON should return 400."""
    headers = {"Content-Type": "application/json"}
    invalid_json = "{\"title\": \"new-post\",,}"
    response = requests.post(f"{SERVER_URL}/posts", data=invalid_json, headers=headers)
    assert response.status_code == 400

def test_dependent_deletion(test_server):
    """DELETE /posts/1?_dependent=comments - Should delete dependent items."""
    # Verify comments exist before deletion
    comments_before = requests.get(f"{SERVER_URL}/comments?postId=1").json()
    assert len(comments_before) == 2

    # Delete the post and its dependent comments
    response = requests.delete(f"{SERVER_URL}/posts/1?_dependent=comments")
    assert response.status_code == 200

    # Verify the post is gone
    post_response = requests.get(f"{SERVER_URL}/posts/1")
    assert post_response.status_code == 404

    # Verify the dependent comments are also gone
    comments_after = requests.get(f"{SERVER_URL}/comments?postId=1").json()
    assert len(comments_after) == 0

def test_sorting_with_null_values(test_server):
    """GET /posts?_sort=views - Should handle nulls correctly."""
    # Add a post with a null view count
    requests.post(f"{SERVER_URL}/posts", json={"id": "4", "title": "null-views", "views": None})
    
    response = requests.get(f"{SERVER_URL}/posts?_sort=views")
    assert response.status_code == 200
    data = response.json()
    # Expect nulls to be sorted first (or last, consistently)
    assert data[0]["views"] is None
    assert data[1]["views"] == 50

def test_serve_nonexistent_static_file(test_server):
    """GET /nonexistent.html - Should return 404."""
    response = requests.get(f"{SERVER_URL}/nonexistent.html")
    assert response.status_code == 404

def test_update_without_id(test_server):
    """PUT /posts without an ID should return 400."""
    response = requests.put(f"{SERVER_URL}/posts", json={"title": "no-id"})
    assert response.status_code == 400

def test_delete_without_id(test_server):
    """DELETE /posts without an ID should return 400."""
    response = requests.delete(f"{SERVER_URL}/posts")
    assert response.status_code == 400

def test_options_method_not_allowed(test_server):
    """OPTIONS /posts should return 405."""
    response = requests.options(f"{SERVER_URL}/posts")
    assert response.status_code == 405

def test_get_nested_on_non_dict(test_server):
    """GET with a nested query on a non-dict should not fail."""
    # Add an item where 'author' is a string, not a dict
    requests.post(f"{SERVER_URL}/posts", json={"id": "5", "title": "bad-nest", "author": "John Doe"})
    # Attempt to filter by a nested property of the string
    response = requests.get(f"{SERVER_URL}/posts?author.name=John")
    assert response.status_code == 200
    # Expect no results because the filter should fail gracefully
    assert len(response.json()) == 0


# --- Final Coverage Tests ---

def test_post_to_root_not_allowed(test_server):
    """POST / should return 404, as it's not a valid resource endpoint."""
    response = requests.post(f"{SERVER_URL}/", json={"key": "value"})
    assert response.status_code == 404


def test_put_with_invalid_json(test_server):
    """PUT /posts/1 with invalid JSON should return 400."""
    headers = {"Content-Type": "application/json"}
    response = requests.put(f"{SERVER_URL}/posts/1", data="{\"a\":,}", headers=headers)
    assert response.status_code == 400


def test_filter_on_nonexistent_nested_field(test_server):
    """GET /posts with a filter on a field that does not exist should return empty."""
    response = requests.get(f"{SERVER_URL}/posts?author.nonexistent=foo")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_embed_with_idless_item(test_server):
    """GET /posts with _embed should not fail if an item has no id."""
    requests.post(f"{SERVER_URL}/posts", json={"title": "no-id-post"})
    response = requests.get(f"{SERVER_URL}/posts?_embed=comments")
    assert response.status_code == 200
    # Ensure the original items are returned, and the id-less one is present
    assert len(response.json()) == 4


# --- Static File Serving ---

def test_serve_static_file(test_server):
    """GET /index.html - Should serve a static file."""
    response = requests.get(f"{SERVER_URL}/index.html")
    assert response.status_code == 200
    assert response.text == "<h1>Hello</h1>"