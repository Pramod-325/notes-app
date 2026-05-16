# Notes Application (Offline-Ready Cloud Sync)

A robust, production-grade monolith API for a basic note-taking application designed with offline-first synchronization in mind. Built with FastAPI (Python) and React.

## 💫 Live Link: https://kaleidoscopic-puffpuff-66a4da.netlify.app/ <br>
## 💫 Base API URL: https://notes-app-09iq.onrender.com/api/v1

## 🚀 Features

* **Offline-Ready Resilience:** Uses `soft_delete` to gracefully handle Delete/Update collisions from offline devices.
* **Secure Authentication:** Employs short-lived JWT access tokens and long-lived, rotated refresh tokens stored in `HttpOnly`, `Secure`, `SameSite=None` cookies to prevent XSS and CSRF attacks.
* **High-Performance Pagination:** Uses SQL Window Functions (`COUNT(*) OVER()`) to fetch paginated items and total counts in a single database round-trip.
* **Idempotent Sharing:** Sharing notes uses PostgreSQL `INSERT ... ON CONFLICT DO NOTHING`, making repeated share requests safe and error-free.
* **Data Export:** In-memory generation of `.zip` archives containing all notes as individual `.txt` files.
* **Defense in Depth:** Enforces note content limits at both the Pydantic schema level and the Service layer to prevent DB row size exhaustion.

---

## 🛠️ Tech Stack

* **Backend:** FastAPI, Python 3.12, Uvicorn
* **Database:** PostgreSQL (NeonDB serverless with PgBouncer), SQLAlchemy (asyncpg), Alembic
* **Security:** raw `bcrypt`, `python-jose` (JWT), SHA-256 for long-password compression
* **Frontend:** React.js, Vite, Axios (with interceptors for token rotation)
* **Deployment:** Render (Backend), Netlify (Frontend)

---

## 🗄️ Database Architecture

<img src="https://github.com/Pramod-325/notes-app/blob/main/notes_app_erd.jpg">

### Core Entities & Relationships:

1.  **`users`**: Stores user accounts.
    * Fields: `id` (UUID), `email` (Unique), `hashed_password`, `full_name`, `is_active`.
2.  **`notes`**: Stores user notes.
    * Fields: `id` (UUID), `owner_id` (FK -> users), `title`, `content`, `is_deleted` (Boolean), timestamps.
    * *Note:* Uses `is_deleted` for soft-deletion to handle offline sync collisions.
3.  **`note_shares`**: Join table managing read access between users and notes.
    * Fields: `note_id` (FK -> notes), `shared_with_user_id` (FK -> users), `shared_by_user_id` (FK -> users), `permission`.
    * *Constraint:* Unique constraint on `(note_id, shared_with_user_id)` for idempotency.
4.  **`refresh_tokens`**: Manages secure session persistence.
    * Fields: `id`, `user_id` (FK -> users), `token_hash` (SHA-256), `revoked`, `expires_at`.

---

## 📡 API Reference

### Auth (`/api/v1/auth`)
* `POST /register` - Create a new user account.
* `POST /login` - Authenticate and receive `access_token` (sets HttpOnly cookie).
* `POST /refresh` - Rotate refresh token and get a new `access_token`.
* `POST /logout` - Revoke all active sessions for the user.

### Notes (`/api/v1/notes`)
* `GET /` - List all owned notes (Paginated, supports `?search=`).
* `POST /` - Create a new note.
* `GET /{id}` - Fetch a specific note (verifies ownership or shared access).
* `PUT /{id}` - Update a note (Owner only).
* `DELETE /{id}` - Soft-delete a note (Owner only).
* `GET /export` - Download a ZIP archive of all owned notes.

### Shares (`/api/v1/notes`)
* `POST /{note_id}/share` - Share a note via email.
* `GET /shared` - List all notes shared *with* the authenticated user.
* `DELETE /{note_id}/share/{email}` - Revoke access for a specific user.

---

## ⚖️ Architecture & Tradeoffs

1.  **Soft Deletes vs. Hard Deletes**
    * *Tradeoff:* Database grows larger over time as "deleted" rows are kept.
    * *Reasoning:* Crucial for offline sync. If Device A deletes a note offline, and Device B edits it offline, a hard delete would cause Device B's sync to silently recreate the note or crash. Soft deletes allow the server to return a `410 Gone` to Device B, rejecting the edit cleanly.
2.  **Stateless JWT vs. Stateful Sessions**
    * *Tradeoff:* Access tokens cannot be revoked instantly without a blocklist.
    * *Reasoning:* Reduces database hits on every request. We mitigate the risk by keeping the access token lifetime very short (15 mins) and enforcing stateful checks on the refresh token.
3.  **Bcrypt 72-Byte Limit**
    * *Tradeoff:* Added computation overhead to hash passwords twice.
    * *Reasoning:* Bcrypt natively crashes if a password exceeds 72 bytes. To allow users to use long passphrases (up to 128 chars), passwords over 72 bytes are pre-hashed using SHA-256 before being fed to Bcrypt.

---

## 🐛 Issues Faced & Resolutions

During development, several specific challenges were encountered and resolved:

### 1. Python 3.14/Rust Build Failure on Render
* **Issue:** Render defaulted to Python 3.14 (pre-release), causing `pip` to attempt to compile `pydantic-core` from source using Rust. This failed due to Render's read-only file system.
* **Fix:** Pinned the `PYTHON_VERSION` environment variable to `3.12.3` in Render, allowing `pip` to download pre-compiled wheels and bypassing the Rust compiler entirely.

### 2. Passlib Deprecation & Bcrypt Crashes
* **Issue:** The `passlib` library relies on a deprecated `__about__` attribute that was removed in `bcrypt 4.0+`. It also threw `ValueError` when running internal self-tests with long strings.
* **Fix:** Completely removed `passlib` from the project. Implemented raw `bcrypt` natively with a custom SHA-256 pre-hashing wrapper to safely handle passwords of any length.

### 3. Cross-Domain Cookie Rejection
* **Issue:** Upon deploying the frontend to Netlify and the backend to Render, the `/refresh` endpoint began failing with `401 Unauthorized` because the HttpOnly cookie was not being sent by the browser.
* **Fix:** Updated the cookie configuration in `auth.py` from `SameSite=Lax` to `SameSite=None` and enforced `Secure=True`. Additionally, ensured `withCredentials: true` was set in the Axios interceptors on the frontend.

### 4. SQLAlchemy Type Hint Collision
* **Issue:** `TypeError: 'function' object is not subscriptable` occurred during app startup in the Repository classes.
* **Fix:** Python confused the `list()` method defined in the Abstract Base Class with the built-in `list` type hint. Resolved by adding `from __future__ import annotations` to evaluate type hints as strings.

---

## 💻 Local Development Setup

1.  **Clone the repository**
2.  **Setup Backend**
    ```bash
    cd backend
    python -m venv .venv
    # Activate on Windows:
    .venv\Scripts\activate

    # Activate on Mac/Linux:
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **🌟Configure Environment (important)**
    Copy `.env.example` to `.env` and fill in your NeonDB PostgreSQL credentials:
    ```env
    DATABASE_URL="postgresql+asyncpg://user:pass@ep-host-pooler.neon.tech/neondb?sslmode=require"

    DATABASE_URL_DIRECT="postgresql+asyncpg://user:pass@ep-host.neon.tech/neondb?sslmode=require"

    JWT_SECRET_KEY="your-32-char-secret"
    ```
    ***🌟 Note: for `DATABASE_URL` keep the connection pooling turned on and for `DATABASE_URL_DIRECT` turned off as shown below: ***
    <img src="https://github.com/Pramod-325/notes-app/blob/main/DB_info.png">

4.  **Initialize DB & Run Server**
    ```bash
    python init_db.py
    uvicorn app.main:app --reload
    ```
5.  **Setup Frontend**
    ```bash
    cd frontend
    npm install
    npm run dev
    ```
