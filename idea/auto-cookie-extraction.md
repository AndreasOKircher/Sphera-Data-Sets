# Idea: Automatic Cookie Extraction for Sphera Downloads

## Problem

Sphera's site uses Cloudflare (`cf_clearance`, `__cf_bm`). These cookies:
- Are tied to your IP address **and** browser User-Agent
- Expire after ~30 minutes
- Cannot be obtained with plain HTTP (Cloudflare requires a real browser to solve the challenge)

The current workflow (copy from DevTools → paste into `cookie.txt`) works but is manual.

## Options (ranked by effort)

### Option A — browser-cookie3 (low effort, may break)
The `browser-cookie3` library reads cookies directly from Chrome/Firefox's local SQLite database.
```
pip install browser-cookie3
```
```python
import browser_cookie3
jar = browser_cookie3.chrome(domain_name="lcadatabase.sphera.com")
cookie_str = "; ".join(f"{c.name}={c.value}" for c in jar)
```
Limitation: Chrome encrypts cookies with DPAPI on Windows — may require running as the same user and can break across Chrome versions.

### Option B — Playwright automation (medium effort, robust)
Use Playwright to open a real browser, log in once, save the session, and reuse cookies.
```
pip install playwright
playwright install chromium
```
Script would:
1. Launch browser, navigate to Sphera login
2. Prompt user to log in manually (or automate if credentials stored)
3. Extract cookies after login
4. Write to `cookie.txt` automatically

This survives Cloudflare because it uses a real browser.

### Option C — Persistent browser session (lowest friction)
Use Playwright with `--save-storage` to persist the full browser session (cookies + localStorage) to a file. Re-use it across runs without re-logging in until the session expires.

## Recommendation

Option B (Playwright) is the most robust long-term solution. It handles Cloudflare correctly and can be scheduled or triggered before each batch run.

## Module scope

This is a Module 2 or standalone utility task — out of scope for Module 1 V1.0.
