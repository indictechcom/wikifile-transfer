# Temp File Cleanup

**Task:** T415717 | **Branch:** `Temp_File_Cleanup_T415717_backend`

---

## Overview

So here's a fun little problem that nobody noticed until someone looked at the server disk space and went, "hm, that's a lot of mystery JPEGs."

Every time a user transferred a file, the app downloaded it to `temp_images/`, did its thing, and then... just left it there. Forever. No cleanup on success. No cleanup on failure. No cleanup if a validation error fired halfway through. The files just piled up like empty pizza boxes in a college dorm — technically harmless at first, but eventually you're going to have a problem.

This PR fixes that. Three things changed:

1. `cleanup_temp_file()` — a shared helper that deletes a temp file without exploding if it doesn't exist
2. Sync uploads in `app.py` — a `try/finally` guarantees cleanup whether the upload succeeded, failed, or blew up mid-validation
3. Async uploads in `tasks.py` — a `_should_cleanup` flag ensures the task cleans up on terminal exit, but leaves the file alone during retries

No new dependencies. No new config. The `temp_images/` directory still works exactly as before — it's just not a permanent archive anymore.

---

## Background — what was actually leaking

There were three leak scenarios, each slightly different:

**Scenario 1: Sync upload succeeds (< 50 MB)**

```
download_image()  →  temp file created ✓
process_upload()  →  file sent to wiki  ✓
route returns     →  temp file... still there ✗
```

The happy path leaked. Every successful upload left a file behind.

**Scenario 2: Validation or auth fails after download**

```
download_image()            →  temp file created ✓
validate target fields      →  ValidationError raised ✗
Flask error handler returns →  temp file... still there ✗
```

If `trproject`, `trlang`, or `trfilename` were missing from the request, or if the user wasn't logged in, the exception blew past the download without anyone cleaning up the file that had just been written to disk. Surprise: the error handler doesn't know about temp files.

**Scenario 3: Async task exits (> 50 MB, success or final failure)**

```
upload_image_task() runs  →  file uploaded (or fails after 3 retries)
task returns result dict  →  temp file... still there ✗
```

The Celery task ran to completion — success or exhausted retries — and just left the file sitting there. The task owns the file for its entire lifetime and is the only thing that can reliably clean it up. But it wasn't.

---

## Files changed

| File | What happened |
|---|---|
| `utils.py` | Added `cleanup_temp_file()` helper; fixed partial-file leak on write failure in `download_image()` |
| `app.py` | `upload()` route now uses `try/finally` to guarantee cleanup for sync uploads |
| `tasks.py` | `upload_image_task()` uses `_should_cleanup` flag + `finally` to clean up on terminal outcomes only |

---

## The helper — `cleanup_temp_file()`

Lives in `utils.py`. Takes a file path, deletes the file if it exists, logs what happened, and returns.

```python
def cleanup_temp_file(file_path):
    """Remove a temp file from disk. Silently ignores missing files."""
    if not file_path:
        return
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except OSError as e:
        logger.warning(f"Failed to remove temp file {file_path}: {e}")
```

It's intentionally boring. It doesn't raise. It doesn't care if the file is already gone (race condition, manual deletion, whatever). It just tries to clean up and logs what it does. If you call it with `None`, it exits immediately — that handles the case where `download_image()` failed before a path was even assigned.

Both `app.py` and `tasks.py` import it from `utils`.

---

## `app.py` — sync upload cleanup

The fix is a `try/finally` block wrapping everything that happens after the download:

```python
file_path = 'temp_images/' + downloaded_filename
handed_off_to_task = False

try:
    # validate fields, check auth, get file size ...

    if file_size < 50 * 1024 * 1024:
        resp = process_upload(...)
        return success_response(data=resp)
    else:
        task = upload_image_task.delay(file_path, ...)
        handed_off_to_task = True
        return success_response(data={"task_id": task.id}, status_code=202)

finally:
    if not handed_off_to_task:
        cleanup_temp_file(file_path)
```

The `handed_off_to_task` flag is the key. For sync uploads (< 50 MB), `finally` always runs — even when a `ValidationError` or `AuthenticationError` is raised before we get to `process_upload()`. The file gets deleted.

For async uploads (> 50 MB), we flip the flag before returning. The `finally` still runs, but sees `handed_off_to_task = True` and skips cleanup. The Celery task owns the file from that point on.

Python's `finally` runs even after a `return` statement — the response is already set when cleanup happens, so there's no timing issue.

---

## `tasks.py` — async task cleanup

Celery tasks have a retry mechanism, which makes cleanup non-trivial. The file needs to survive retries (otherwise attempt #2 opens a file that no longer exists) but get deleted once the task is truly done.

The solution is a `_should_cleanup` flag:

```python
_should_cleanup = True  # flipped to False only before self.retry()

try:
    ...
    except requests.exceptions.Timeout as e:
        if self.request.retries < self.max_retries:
            _should_cleanup = False   # ← file must survive the retry
            raise self.retry(exc=e)
    ...
    except Retry:
        raise   # ← _should_cleanup is False here, finally won't delete the file

    except Exception as e:
        ...
        return {"success": False, ...}

finally:
    if _should_cleanup:
        cleanup_temp_file(file_path)
```

When `self.retry()` is called:
- `_should_cleanup` is set to `False`
- `self.retry()` raises a `Retry` exception
- `except Retry: raise` re-raises it
- `finally` runs — sees `_should_cleanup = False` — skips cleanup
- Celery reschedules the task with the file still on disk

When the task exits for real (success, final failure, or unexpected exception):
- `_should_cleanup` is still `True`
- `finally` runs — sees `_should_cleanup = True` — deletes the file

**Why not just put cleanup in each `return` statement?**

The task has fourteen return points. Adding `cleanup_temp_file(file_path)` before each one would work, but it's fragile — someone adds a new early return someday and forgets the cleanup line, and we're back to leaking. The flag-plus-finally approach makes cleanup automatic for any path through the code, as long as it's not a retry.

---

## The partial-file edge case in `download_image()`

There was a smaller leak in `utils.py` that's also fixed here. If `f.write(r.content)` raised an `OSError` partway through writing:

```python
with open(file_path, "wb") as f:
    f.write(r.content)   # ← OSError here closes the handle but leaves the partial file
```

The file handle gets closed (the `with` handles that), but a partial file stays on disk. The existing `except OSError` handler logged and re-raised, but didn't clean up. Now it does:

```python
except OSError as e:
    partial = file_path if "file_path" in locals() else None
    cleanup_temp_file(partial)
    ...
    raise FileOperationError(...) from e
```

This is a rare case — disk-full or permissions errors — but partial files are worse than no files, so we clean them up.

---

## Testing

The existing test suite covers the behaviour changes:

- `tests/utils_test.py` — disk write failure → `FileOperationError` raised (partial cleanup tested implicitly via mock)
- `tests/tasks_test.py` — retry scenarios verify the task re-raises `Retry` correctly; terminal failure scenarios verify the dict is returned
- `tests/app_test.py` — validation-fail-after-download scenarios return the expected 400; sync upload success returns 200

**Run the full suite:**

```bash
pytest tests/ -v
```

**Manually check cleanup is happening:**

```bash
# watch the log while running a transfer
tail -f logs/wikifile-transfer.log | grep "temp"

# before the fix, this directory would grow indefinitely
ls -la temp_images/
```

After a successful transfer, `temp_images/` should be empty (or contain only files from in-flight requests). If you see files accumulating, something isn't being cleaned up — check the log for "Failed to remove temp file" warnings.

---

## What this doesn't change

- The `temp_images/` directory is still created automatically by `download_image()` if it doesn't exist
- No changes to the upload API contract — request/response shape is identical
- No changes to retry behavior — still 3 retries, 60s delay, same retry conditions
- No new dependencies

---

## Adding cleanup to new upload paths

If you add a new route that calls `download_image()`, the pattern is:

```python
filename = download_image(...)
file_path = f"temp_images/{filename}"
handed_off = False

try:
    # ... your route logic
    if async_path:
        some_task.delay(file_path, ...)
        handed_off = True
        return ...
    else:
        do_sync_thing(file_path)
        return ...
finally:
    if not handed_off:
        cleanup_temp_file(file_path)
```

And if you add a new Celery task that receives a `file_path`, follow the `_should_cleanup` pattern from `tasks.py`. The `finally` approach is the right one — don't try to add cleanup at every individual return statement.
