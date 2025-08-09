# Simple JSON Server

[![PyPI version](https://badge.fury.io/py/simple-json-server.svg)](https://badge.fury.io/py/simple-json-server)
[![PyPI Downloads](https://static.pepy.tech/badge/simple-json-server)](https://pepy.tech/projects/simple-json-server)
[![Python Version](https://img.shields.io/pypi/pyversions/simple-json-server.svg)](https://pypi.org/project/simple-json-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI/CD Pipeline](https://github.com/10mohi6/simple-json-server/actions/workflows/publish-to-pypi.yml/badge.svg)](https://github.com/10mohi6/simple-json-server/actions/workflows/publish-to-pypi.yml)
[![Coverage Status](https://codecov.io/gh/10mohi6/simple-json-server/branch/main/graph/badge.svg)](https://codecov.io/gh/10mohi6/simple-json-server)

A zero-dependency, lightweight REST API server based on a simple JSON file, built with Python's standard `http.server` module. This project provides a quick and easy way to set up a mock API for frontend development, prototyping, or any scenario where a real backend is not yet available.

Inspired by `json-server`.

## Features

- **Zero Dependencies:** Runs with just a standard Python installation.
- **Web Admin Interface:** A browser-based UI to view, add, edit, and delete data and resources.
- **RESTful API:** Automatically generates a full REST API from a `db.json` file.
- **CRUD Operations:** Supports `GET`, `POST`, `PUT`, `PATCH`, and `DELETE` methods.
- **Advanced Querying:** Filter, sort, and paginate your responses.
- **Full-text Search:** Perform a simple text search across all fields in a resource.
- **Relationships:** Supports both parent (`_expand`) and child (`_embed`) relationships.
- **Cascading Deletes:** Delete dependent resources automatically using `_dependent`.
- **Static File Serving:** The admin UI is bundled with the package. You can also serve your own static files from a `public` directory.

## Installation

You can install the package from PyPI:

```bash
pip install simple-json-server
```

## Usage

1.  **Create a `db.json` file (optional):**
    In your project directory, create a `db.json` file. The keys will be treated as API resources. If you don't create one, the server will start with an empty database.

    ```json
    {
      "posts": [
        { "id": "1", "title": "json-server", "views": 100, "authorId": "1" }
      ],
      "authors": [
        { "id": "1", "name": "Alice" }
      ]
    }
    ```

2.  **Start the server:**
    Run the following command in your project directory:
    ```bash
    simple-json-server
    ```

    The server will be running at `http://127.0.0.1:5000`.

### Command-Line Options

You can customize the server's behavior with the following options:

- **Port:** Run on a different port.
  ```bash
  simple-json-server --port 8080
  ```

- **Host:** Make the server accessible on your local network.
  ```bash
  simple-json-server --host 0.0.0.0
  ```

- **Database File:** Use a different database file.
  ```bash
  simple-json-server --file my_api_data.json
  ```

## Admin Interface

An admin UI is bundled with the server to easily manage your data.

- **URL:** `http://127.0.0.1:5000/admin.html`

**Features:**
- **Resource Management:** Add, rename, and delete resources (e.g., `posts`, `users`) directly from the UI.
- **Data Management:** View, add, edit, and delete individual data entries within a resource using a JSON editor.
- **Query Tester:** A simple interface to test your API endpoints with different query parameters.

## API Endpoints

Based on the `db.json` example above, the following endpoints are available:

### Query Parameters

- **Sort:** `GET /posts?_sort=-views` (Sort by views, descending) or `GET /posts?_sort=title` (Sort by title, ascending).
- **Filter:** `GET /posts?views_gte=200` (Get posts with views >= 200). Operators: `_ne`, `_lt`, `_lte`, `_gt`, `_gte`.
- **Paginate:**
    - `GET /posts?_page=1&_per_page=10` (Page-based pagination)
    - `GET /posts?_start=0&_end=10` (Slice from index 0 to 10)
    - `GET /posts?_start=10&_limit=5` (Slice 5 items starting from index 10)
- **Full-text Search:** `GET /posts?_q=python` (Search for "python" in any field).
- **Relationships:**
    - `GET /posts/1?_expand=author` (Include the parent `author` resource).
    - `GET /authors/1?_embed=posts` (Include the children `posts` resources).
- **Cascading Delete:** `DELETE /posts/1?_dependent=comments` (Delete post 1 and all its associated comments).

## Static File Serving

If you create a `public` folder in the directory where you run the server, it will be used to serve your own static files, overriding the bundled admin UI if there are name conflicts (e.g., `index.html`).

## Development

To contribute to development, clone the repository and install the testing dependencies.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/10mohi6/simple-json-server.git
   cd simple-json-server
   ```

2. **Install dev dependencies:**
   It's recommended to use `uv` for managing the environment.
   ```bash
   uv pip install -e .[dev]
   ```

3. **Run tests:**
   To run tests and see the coverage report in the terminal:
   ```bash
   uv run pytest --cov=simple_json_server --cov-report=term-missing
   ```

## Publishing to PyPI

This project is automatically published to PyPI via GitHub Actions. A new version is released whenever a push is made to the `main` branch.