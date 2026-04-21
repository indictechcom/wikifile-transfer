# Error Handling & Exception Architecture

**Task:** T415715 | **Branch:** `Error_Handling_T415715_backend`

---

## Overview

So... the backend had a real problem. Bare `except:` blocks everywhere, routes returning completely different shaped responses depending on who wrote them, and async task failures that just disappeared into thin air. No log entry, no error to the client, nothing. You'd get a broken response and spend an hour figuring out why.

This PR fixes that. Five things changed:

1. Custom exception hierarchy — so you know *what* failed, not just "something went wrong"
2. Structured rotating log files — so failures are actually recorded and searchable
3. Every bare `except:` replaced with typed catches and proper `raise X from e` chaining
4. Every API endpoint returns the same JSON shape whether it succeeds or fails
5. Celery task errors are captured, logged, and returned instead of silently vanishing

No new dependencies. Everything uses Python's built-in `logging` module.

---

## Background — what the code looked like before

Here's roughly what error handling looked like before this:

```python
try:
    result = do_the_thing()
except:  # catches EVERYTHING, including KeyboardInterrupt
    return None  # good luck figuring out what happened
```

Routes returned different things on failure. Some returned `{"error": "..."}`, some returned `{"success": False}`, some just returned `None` and let the caller figure it out. The frontend was essentially guessing what shape it was going to get.

The deeper problem was the silent failures. A download would fail, `None` would bubble up through the call stack, and the route would keep running as if everything was fine. No log entry, no error to the client, just a broken response that looked like a success. That's the kind of bug that shows up in production and takes way too long to track down.

---

## Files added / changed

| File | What happened |
|---|---|
| `exceptions.py` | New — custom exception hierarchy |
| `error_handlers.py` | New — Flask handler registration and JSON response builders |
| `logging_config.py` | New — structured rotating log files, helper functions |
| `utils.py` | Bare `except` blocks → typed catches with `raise X from e` chaining |
| `app.py` | Routes now raise exceptions; `register_error_handlers()` wired at startup |
| `tasks.py` | Per-step error handling, retry logic, structured logging, Celery `Retry` re-raise guard |
| `tests/utils_test.py` | New — mocked unit tests for all three util functions |
| `tests/tasks_test.py` | New — mocked unit tests for the async upload task with retry logic |
| `tests/app_test.py` | New — Flask test client integration tests for every route in the app |

---

## Configuration

**No new dependencies** — `pip install -r requirements.txt` is all you need.

**Log directory** — `logs/` is created automatically the first time the app starts. You don't need to create it manually. If you want logs written somewhere else:

```python
setup_logging(log_dir="/your/path")
```

**Environment flag** — the only thing that changes between dev and production:

```python
setup_logging()           # production — log files only, no console noise
setup_logging(env="dev")  # development — log files + console output
```

Called once in `app.py` at startup. In dev it's useful to see logs in the terminal without opening a file. In production, don't spam stdout.

The three log files written to `logs/`:

```
wikifile-transfer.log              # human-readable, INFO and above
wikifile-transfer-error.log        # ERROR and CRITICAL only — for quick scans
wikifile-transfer-structured.jsonl # same events as JSON, one object per line
```

All three rotate at 10MB and keep 5 backups. The `.jsonl` file is mainly useful if you're piping logs into a log aggregator — each line is a valid JSON object you can parse directly.

> Pro tip: run `tail -f logs/wikifile-transfer.log` in a separate terminal while testing. You'll see everything happening in real time instead of digging through the file.

---

## How it's structured

Four files, each doing exactly one thing:

```
exceptions.py      → defines what can go wrong  (domain vocabulary)
error_handlers.py  → decides what the client sees  (HTTP responses)
logging_config.py  → decides what gets recorded  (log files)
utils/app/tasks.py → where things actually fail  (raises the exceptions)
```

The separation is intentional. If you want to change `WikiAPIError` from 502 to 503, you change one line in `error_handlers.py`. You don't touch any of the `utils.py` code where that exception is raised. That's the whole point — presentation and business logic don't mix.

---

## exceptions.py — naming what went wrong

Everything inherits from `WikifileTransferError`. The base class stores three things: a human-readable `message`, a machine-readable `error_code` string, and a `details` dict for any extra context.

```
WikifileTransferError (base)
│
├── ValidationError         — bad user input (missing fields, wrong URL format)
├── WikiAPIError            — MediaWiki API failures (timeouts, bad status codes, unexpected response shape)
├── FileOperationError      — download, write, or read failures on disk
├── DatabaseError           — SQLAlchemy commit failures
├── OAuthError              — token exists but is broken or rejected by the wiki
├── AuthenticationError     — user has no session at all
├── UploadError             — wiki accepted the request but rejected the upload
├── ConfigurationError      — missing or broken config.yaml entries
├── TaskError               — Celery async task-level failures
└── ResourceNotFoundError   — image or file doesn't exist on the source wiki
```

Each subclass takes specific keyword arguments that get stored in `details`. `WikiAPIError` takes `api_endpoint` and `status_code`. `FileOperationError` takes `operation` and `file_path`. That context travels with the exception from where it's raised, through the handler, all the way into the log entry and client response. Which means when something breaks, you actually know where and why — not just "an error occurred."

**Why not just use  HTTPException directly?**

Because `WikiAPIError` is a domain concept, not an HTTP concept. It means "the MediaWiki API did something unexpected." That it maps to 502 is the *handler's* decision, not the exception's. If those concerns are mixed, every status code change means digging through business logic to find where exceptions are raised. Not worth it.

---

## error_handlers.py — what the client sees

`register_error_handlers(app)` is called once at startup in `app.py`. It wires each exception class to a handler using Flask's `app.register_error_handler()`. When a route raises `WikiAPIError(...)`, Flask intercepts it before anything reaches the client and calls the right handler automatically.

Every response — success or failure — has the same outer shape:

```json
{
  "success": false,
  "data": {},
  "errors": ["Timeout while fetching image info"],
  "error_details": {
    "code": "WIKI_API_ERROR",
    "message": "Timeout while fetching image info",
    "details": { "api_endpoint": "https://en.wikipedia.org/w/api.php" }
  }
}
```

`success` is always boolean. `errors` is always a list. `error_details.code` is always one of the strings defined in `exceptions.py`. The frontend never has to guess what shape it's getting.

**HTTP status codes:**

| Exception | Status | Why |
|---|---|---|
| `ValidationError` | 400 | client sent something wrong |
| `AuthenticationError` | 401 | no session at all |
| `OAuthError` | 401 | session exists but token is broken |
| `ResourceNotFoundError` | 404 | image doesn't exist on source wiki |
| `WikiAPIError` | 502 | upstream wiki API failed — bad gateway |
| `FileOperationError` | 500 | server-side disk failure |
| `DatabaseError` | 500 | internal — real message hidden from client |
| `ConfigurationError` | 500 | internal — real message hidden from client |
| `UploadError` | 500 | wiki rejected the upload |
| `TaskError` | 500 | async task failed |
| `Exception` (catch-all) | 500 | anything we didn't anticipate |

`DatabaseError` and `ConfigurationError` intentionally show the client a generic message ("please contact the administrator") instead of the real one. You really don't want internal database operation names or config key values leaking to users. The actual message still goes to the logs where it's useful.

---

## logging_config.py — structured logging

**Helper functions used throughout the app:**

`log_exception(logger, e, extra_context={})` — logs the full stack trace plus any extra context you pass. Use this when you're catching something and want the traceback recorded before re-raising.

`log_timed_api_call(logger, endpoint, method)` — context manager that wraps any HTTP call and records how long it took, the status code, and whether it threw. Every `requests.get()` and `requests.post()` in `utils.py` and `tasks.py` is wrapped in this:

```python
with log_timed_api_call(logger, src_endpoint, "GET") as context:
    response = requests.get(...)
    context["status_code"] = response.status_code
    # setting status_code here tells the context manager what to log
    # it reads it in the else block after the with exits cleanly
```

`log_file_operation(logger, operation, file_path, success, error)` — records download, upload, and write events with the outcome. Gives you a paper trail of every file the app touched.

`log_task_event(logger, task_id, task_name, status, error, progress)` — logs Celery task lifecycle events with the task ID on every line. Without the task ID attached, tracing a single async task through multiple log entries is really painful.

---

## Exception chaining — `raise X from e`

This is the most important pattern in `utils.py`. Every time a low-level exception is caught and re-raised as a domain exception, it uses `from e`:

```python
except requests.exceptions.Timeout as e:
    raise WikiAPIError(
        f"Timeout while fetching image info for {src_filename}",
        api_endpoint=src_endpoint,
        details={"timeout_seconds": 30}
    ) from e
```

The `from e` sets `__cause__` on the new exception. Without it, the original `requests.Timeout` disappears from the traceback — you only see the `WikiAPIError`. With it, you see both: the domain-level failure *and* the underlying cause that triggered it.

When you're debugging a production failure, you need both. "The wiki API timed out" is useful. "The wiki API timed out because of *this specific connection error*" is actually actionable.

---

## utils.py — two-phase handling and per-article resilience

`download_image()` has two separate try/except blocks instead of one combined one. The first covers fetching image metadata from the API. The second covers downloading the actual file bytes.

This was deliberate. One big block would raise the same exception whether the image wasn't found on the wiki, or whether it was found but the download failed halfway. Those are different failures with different causes and they get different exceptions and different messages — `ResourceNotFoundError` vs `FileOperationError`.

`get_localized_wikitext()` takes a completely different approach. Each per-article langlink lookup is wrapped individually inside the loop, and failures just log a warning and `continue`. If the Wikipedia API is flaky for one article title, that one gets skipped — the rest of the templates still get processed. The function never throws. The outer `except Exception` at the very end is a safety net that returns the original unmodified wikitext if something goes badly wrong with the parser itself. Better to return something than to crash the whole request.

---

## app.py — routes raise, handlers respond

Routes don't build error responses anymore. They raise typed exceptions and let the registered handlers deal with them:

```python
ses = authenticated_session()
if ses is None:
    raise AuthenticationError("You must be logged in to upload files")
```

Flask catches the `AuthenticationError`, finds the registered handler, returns the 401 JSON response. The route code never calls `jsonify` for errors — it only cares about the happy path.

`register_error_handlers(app)` runs once at startup. That's the only place exception classes are connected to handler functions.

---

## tasks.py — async tasks never raise, always return

Celery tasks run outside the Flask request context, so Flask's error handlers don't apply here. The approach is different: **tasks catch everything and always return a dict.**

```python
return {"success": False, "data": {}, "errors": [error_msg]}
# or on success:
return {"success": True, "wikipage_url": ..., "file_link": ...}
```

The frontend polls `/api/task_status/<task_id>` and reads `result.success`. No exception propagation — the task absorbs failures and encodes the outcome in the return value.

One thing that tripped me up: Celery's own `Retry` exception **must** be re-raised, not caught. If you swallow it and return a dict, Celery thinks the task completed successfully and stops retrying entirely. The `except Retry: raise` block at the bottom of the task is there specifically for this — don't remove it.

Network timeouts trigger `self.retry(exc=e)` when retries remain (max 3, 60s delay). `AuthenticationError` skips the retry entirely — there's no point retrying with an expired OAuth token, it'll fail the same way every single time.

---

## OAuthError vs AuthenticationError

These two look similar but they're describing completely different situations, and getting them confused leads to the wrong error message reaching the user.

**`AuthenticationError`** — the user simply isn't logged in. Either they never went through the OAuth flow, or their session cookie expired and got cleared. The fix is: log in again. Nothing is broken, the session just doesn't exist.

**`OAuthError`** — the user *did* log in. The token exists in the session. But when that token is sent to the wiki, the wiki rejects it. This happens when the consumer application gets deregistered on the wiki side, or when a token is manually revoked. The session cookie looks valid on our end, but the wiki won't accept it. Both return 401, but the underlying cause is totally different.

There's also a third case that's easy to miss entirely — the `+\` CSRF token check in `process_upload()`:

```python
csrf_token = response.json()["query"]["tokens"]["csrftoken"]

if csrf_token == "+\\":
    raise AuthenticationError("Invalid CSRF token — OAuth session may have expired")
```

`+\` is the literal string MediaWiki returns for a CSRF token when it doesn't recognize the OAuth session. The HTTP response is still 200. No error code, no exception from `requests`, nothing to catch automatically. It's a semantic failure hidden inside a perfectly valid HTTP response — if you don't check for it explicitly, the upload proceeds with that bad token and fails later in a confusing way with no clear error. The explicit check catches it before it gets that far.

In short:
- No session at all → `AuthenticationError`
- Session exists, wiki rejects the token → `OAuthError`
- Session exists, wiki returns `+\` CSRF token → `AuthenticationError` (OAuth session isn't being recognized)

---

## Testing

Three test files. Each one covers a different layer of the stack, and each one is completely offline — no Wikipedia, no Redis, no MySQL, no actual network traffic of any kind. The test suite should run just as happily on a plane with no Wi-Fi as it does in CI. (Tested. It does.)

**Run everything at once:**

```bash
pytest tests/ -v
```

**Or target a specific file:**

```bash
pytest tests/utils_test.py -v    # utility functions
pytest tests/tasks_test.py -v    # async Celery task
pytest tests/app_test.py -v      # Flask routes end to end
```

---

### tests/utils_test.py — the utility layer

This is where the low-level networking lives: fetching image metadata, downloading the file, uploading to the target wiki, and localizing wikitext templates. All three functions in `utils.py` are covered here.

`download_image()`:
- Happy path returns a filename string with the correct extension
- Metadata timeout → `WikiAPIError`, not `None`, not a generic `Exception`
- Image download timeout → `FileOperationError` (different exception, different phase — the test actually verifies they're different types, not just that something was raised)
- File missing on source wiki → `ResourceNotFoundError`
- Disk write failure → `FileOperationError`
- `iilocalonly` param is confirmed to be sent in the request (this matters — it's why Commons-hosted files sometimes return no imageinfo, and knowing it's intentionally there vs accidentally there is worth having in writing)

`process_upload()`:
- CSRF token `"+\\"` → `AuthenticationError`, caught before the upload even starts
- CSRF request timeout → `WikiAPIError`
- Missing keys in CSRF response → `WikiAPIError`
- File missing before upload → `FileOperationError`
- `OSError` reading the file → `FileOperationError`
- Upload result `!= "Success"` → `WikiAPIError` with the wiki's own error message included in the exception
- Upload says Success but no `imageinfo` in the response → `WikiAPIError` (MediaWiki says "it worked" but gives you nothing useful — that's a failure, treat it as one)

`get_localized_wikitext()`:
- Per-article timeout → skipped with a warning, processing continues for the remaining templates
- Per-article request error → same — one article failing doesn't abort everything else
- Parser crash → original wikitext returned unchanged, nothing raised
- Template not in `TEMPLATES` → no API call made, ignored silently

---

### tests/tasks_test.py — the async task layer

Celery tasks have a different failure model than Flask routes. They can't raise to the client. They can't use Flask error handlers. And they have retry logic on top of all that, which means the same network error can either trigger a retry or return a failure dict depending on how many attempts have already happened.

The mock used here is worth knowing about. Every test gets a fake "Celery self" object that has `self.request.id`, `self.request.retries`, `self.max_retries`, and a `self.retry()` that raises `celery.exceptions.Retry` exactly like the real one does. This lets tests verify retry behavior without Celery running at all.

`upload_image_task()`:
- Happy path returns `{"success": True}` with correct `wikipage_url` and `file_link`
- CSRF token from the GET request appears in the upload POST — verifies the token is actually being threaded through
- Missing OAuth credentials → immediate failure dict, no network calls
- Single missing OAuth key → failure dict with the key name in the error message
- OAuth session creation failure → failure dict with helpful message
- Anonymous CSRF token `"+\\"` → failure dict, **no retry** (retrying with a dead token is a waste of everyone's time)
- CSRF timeout with retries remaining → raises `Retry` (Celery picks this up and reschedules)
- CSRF timeout with retries exhausted → failure dict with "Timeout" in the error
- CSRF network error → triggers retry
- CSRF response missing expected keys → failure dict, no retry (this is a logic error, not a transient failure — retrying won't fix a broken response)
- File not found on disk → failure dict
- `OSError` reading file → failure dict
- Upload timeout with retries remaining → raises `Retry`
- Upload timeout with retries exhausted → failure dict
- Upload network error → triggers retry
- Upload result is `"Failure"` → failure dict with the wiki's own error message
- Upload succeeds but `imageinfo` is missing → failure dict

---

### tests/app_test.py — the Flask route layer

This one is a bit more involved because it's testing the actual HTTP layer — request parsing, route logic, error handler wiring, database reads and writes, the works. It uses Flask's test client with an in-memory SQLite database so no MySQL server is needed.

**The one interesting setup trick:** `flask_mwoauth` is stubbed in `sys.modules` before `app.py` is imported. This replaces the real `MWOAuth` object with a `MagicMock`, which means tests can control `MW_OAUTH.get_current_user.return_value` directly without needing a real OAuth session. The blueprint it registers is a real Flask `Blueprint` (not a mock) so `app.register_blueprint()` doesn't complain.

**POST /api/upload:**
- Empty body → 400 `VALIDATION_ERROR`
- `srcUrl` not a wiki URL → 400 `VALIDATION_ERROR`
- `download_image` returns `None` → 500 `FILE_OPERATION_ERROR`
- Missing target fields (`trproject`, `trlang`, `trfilename`) → 400 `VALIDATION_ERROR`
- No OAuth session → 401 `AUTHENTICATION_ERROR`
- File under 50MB, upload succeeds → 200, response includes `source` URL
- File over 50MB → 202 with `task_id` from the queued Celery task

**GET /api/preference:**
- Unauthenticated → 200 with defaults (`wikipedia`, `en`, `skip_upload_selection: false`)

**POST /api/preference:**
- Missing `project` → 400
- Missing `lang` → 400
- Unauthenticated → 401
- Authenticated save → 200 (creates a new User row)
- Same user, second POST → 200 (updates the existing row, doesn't insert a duplicate)
- GET after POST reflects the saved values — this is the closest to an integration test in the suite

**GET /api/user_language:**
- Unauthenticated → 200 with `"user_language": "en"`

**POST /api/user_language:**
- Missing `user_language` → 400
- Unauthenticated → 401
- Authenticated save → 200
- GET after POST reflects the saved language

**GET /api/get_wikitext:**
- No query params → 200 with empty wikitext (the UI handles this case gracefully — no point erroring)
- Partial params → same
- All params, API responds → 200 with localized wikitext
- All params, no revisions in response → 200 with empty wikitext
- API timeout → 502
- Connection error → 502

**POST /api/edit_page:**
- Missing `targetUrl` → 400
- Missing `content` → 400
- `targetUrl` is not a wiki URL → 400
- Unauthenticated → 401
- CSRF fetch times out → 502
- `+\` CSRF token → 401 (expired OAuth session, same check as in `process_upload`)
- Valid CSRF token, edit POST succeeds → 200

**GET /api/user:**
- Not logged in → 200 with `{"logged": false, "username": null}`
- Logged in → 200 with `{"logged": true, "username": "WikiUser123"}`

**GET /api/task_status/\<task_id\>:**
- PENDING task → 200 with `task_id`, `status`, `result: null`
- SUCCESS task → 200 with `result` populated
- FAILURE task → 200 with `error` field containing the exception message

---

**Manually verifying the API response shape:**

Start the app and send a bad request:

```bash
curl -X POST http://localhost:5000/api/upload \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected response (HTTP 400):

```json
{
  "success": false,
  "data": {},
  "errors": ["srcUrl is required"],
  "error_details": {
    "code": "VALIDATION_ERROR",
    "message": "srcUrl is required",
    "details": { "field": "srcUrl" }
  }
}
```

If you're seeing a plain HTML Flask error page instead of this JSON, `register_error_handlers(app)` didn't run — check `app.py` startup. If you're seeing a 200 with no body, you've got a bigger problem and maybe take a break first.

**Check logs are being written:**

```bash
# Watch everything in real time
tail -f logs/wikifile-transfer.log

# Find specific errors fast
grep "UPLOAD_ERROR" logs/wikifile-transfer.log

# Parse the structured log if you need to
python3 -c "
import json
with open('logs/wikifile-transfer-structured.jsonl') as f:
    for line in f:
        entry = json.loads(line)
        if entry['level'] == 'ERROR':
            print(entry['timestamp'], entry['message'])
"
```

---

## Adding a new exception

1. Add the class to `exceptions.py` inheriting from `WikifileTransferError`. Pick a specific `error_code` — make it obvious (`RATE_LIMIT_ERROR` not `ERROR_7`).
2. Add a handler in `error_handlers.py` calling `create_error_response()` with the right HTTP status.
3. Register it in `register_error_handlers()`.
4. Raise it in application code with `raise YourNewError("message", ...)`.

Don't skip step 3. Flask falls through to `handle_generic_exception()` for anything unregistered, which returns a generic 500 and throws away all the structured context the exception was carrying. You'll spend time wondering why your nicely typed exception turned into a useless 500 with no details.
