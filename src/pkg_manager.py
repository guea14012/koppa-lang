"""
KOPPA Package Manager
Like pip for Python or npm for Node — install community KOPPA modules.

Usage (via koppa CLI):
    koppa pkg install <name>          # install from registry
    koppa pkg install <github-url>    # install from GitHub repo
    koppa pkg uninstall <name>        # remove package
    koppa pkg list                    # list installed packages
    koppa pkg search <query>          # search registry
    koppa pkg init                    # create koppa.json in current dir
    koppa pkg update                  # update all packages
    koppa pkg login [--token TOKEN]   # login to registry
    koppa pkg logout                  # logout
    koppa pkg whoami                  # show current user
    koppa pkg publish                 # publish current package
    koppa pkg token                   # show API token
"""

import json
import shutil
import urllib.request
import urllib.error
import urllib.parse
import zipfile
import tempfile
import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

KOPPA_HOME    = Path.home() / ".koppa"
PACKAGES_DIR  = KOPPA_HOME / "packages"
REGISTRY_CACHE = KOPPA_HOME / "registry.json"

REGISTRY_URL = (
    "https://raw.githubusercontent.com/guea14012/koppa-registry-/main/index.json"
)
REGISTRY_WEB  = "https://guea14012.github.io/koppa-registry-"
AUTH_FILE     = KOPPA_HOME / "auth.json"

# Supabase config — mirrors www/_config.js
# Update these after creating your Supabase project
SUPABASE_URL      = "https://uovrlnnwzaqkjsnqhxvq.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVvdnJsbm53emFxa2pzbnFoeHZxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc0ODQxMDcsImV4cCI6MjA5MzA2MDEwN30.WpIBO6duMHUKctnR1d74smB9h2swDfe0-rYEAucf1ns"

# Bundled fallback registry (works offline for built-ins)
BUILTIN_REGISTRY = {
    "packages": {}
}


def _ensure_dirs():
    KOPPA_HOME.mkdir(parents=True, exist_ok=True)
    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)


def _fetch_registry() -> dict:
    """Download registry index; fall back to cached or built-in."""
    try:
        with urllib.request.urlopen(REGISTRY_URL, timeout=5) as r:
            data = json.loads(r.read())
            REGISTRY_CACHE.write_text(json.dumps(data, indent=2))
            return data
    except Exception:
        if REGISTRY_CACHE.exists():
            return json.loads(REGISTRY_CACHE.read_text())
        return BUILTIN_REGISTRY


def _installed_manifest() -> dict:
    """Read installed packages manifest."""
    manifest_path = KOPPA_HOME / "installed.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    return {}


def _save_manifest(data: dict):
    (KOPPA_HOME / "installed.json").write_text(json.dumps(data, indent=2))


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_install(name: str):
    """Install a KOPPA package by name or GitHub URL."""
    _ensure_dirs()

    # Detect GitHub URL
    if name.startswith("https://github.com/") or name.startswith("github.com/"):
        url = name if name.startswith("http") else "https://" + name
        _install_from_github(url)
        return

    # Lookup in registry
    registry = _fetch_registry()
    pkg = registry.get("packages", {}).get(name)
    if not pkg:
        print(f"[!] Package '{name}' not found in registry.")
        print("    Try:  koppa pkg search <query>")
        print("    Or install directly:  koppa pkg install https://github.com/user/repo")
        return

    _install_from_github(pkg["url"], name, pkg.get("version", "latest"))


def _install_from_github(url: str, pkg_name: str = None, version: str = "latest"):
    """Download and install a package from GitHub."""
    # Normalise: https://github.com/user/repo → zip URL
    if "github.com" in url and not url.endswith(".zip"):
        # Convert to zip archive URL
        parts = url.rstrip("/").split("/")
        if len(parts) >= 5:
            user, repo = parts[-2], parts[-1]
        else:
            print(f"[!] Cannot parse GitHub URL: {url}")
            return
        pkg_name = pkg_name or repo
        zip_url = f"https://github.com/{user}/{repo}/archive/refs/heads/main.zip"
    else:
        zip_url = url
        pkg_name = pkg_name or url.split("/")[-1].replace(".zip", "")

    print(f"[~] Installing {pkg_name} from {zip_url} ...")

    try:
        with urllib.request.urlopen(zip_url, timeout=30) as r:
            zip_data = r.read()
    except urllib.error.URLError as e:
        print(f"[!] Download failed: {e}")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "pkg.zip"
        zip_path.write_bytes(zip_data)

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)

        # Find extracted directory (GitHub adds -main suffix)
        extracted = [d for d in tmp_path.iterdir() if d.is_dir()]
        if not extracted:
            print("[!] Archive is empty")
            return
        src_dir = extracted[0]

        # Install to packages dir
        dest = PACKAGES_DIR / pkg_name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src_dir, dest)

    # Update manifest
    manifest = _installed_manifest()
    manifest[pkg_name] = {"version": version, "url": zip_url}
    _save_manifest(manifest)

    print(f"[+] Installed: {pkg_name} → {dest}")
    print(f"    Use with:  import {pkg_name}")


def cmd_uninstall(name: str):
    """Remove an installed package."""
    dest = PACKAGES_DIR / name
    if not dest.exists():
        print(f"[!] Package '{name}' is not installed.")
        return
    shutil.rmtree(dest)
    manifest = _installed_manifest()
    manifest.pop(name, None)
    _save_manifest(manifest)
    print(f"[-] Uninstalled: {name}")


def cmd_list():
    """List installed packages."""
    _ensure_dirs()
    manifest = _installed_manifest()
    if not manifest:
        print("No packages installed.")
        print(f"Install with:  koppa pkg install <name>")
        return
    print(f"Installed packages ({PACKAGES_DIR}):")
    for name, info in manifest.items():
        print(f"  {name:20s}  {info.get('version', '?')}")


def cmd_search(query: str):
    """Search the package registry."""
    registry = _fetch_registry()
    packages = registry.get("packages", {})
    if not packages:
        print("Registry is empty or unavailable.")
        return
    results = {
        k: v for k, v in packages.items()
        if query.lower() in k.lower() or query.lower() in v.get("description", "").lower()
    }
    if not results:
        print(f"No packages matching '{query}'")
        return
    print(f"{'Name':20s}  {'Version':10s}  Description")
    print("-" * 60)
    for name, info in results.items():
        print(f"{name:20s}  {info.get('version', '?'):10s}  {info.get('description', '')}")


def cmd_init():
    """Create a koppa.json in the current directory."""
    manifest_path = Path("koppa.json")
    if manifest_path.exists():
        print("koppa.json already exists.")
        return
    manifest = {
        "name": Path.cwd().name,
        "version": "1.0.0",
        "description": "",
        "main": "main.kop",
        "dependencies": {}
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print("[+] Created koppa.json")


def cmd_update():
    """Update all installed packages."""
    manifest = _installed_manifest()
    if not manifest:
        print("No packages installed.")
        return
    for name, info in list(manifest.items()):
        print(f"[~] Updating {name} ...")
        _install_from_github(info["url"], name)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _load_auth() -> dict:
    if AUTH_FILE.exists():
        return json.loads(AUTH_FILE.read_text())
    return {}

def _save_auth(data: dict):
    KOPPA_HOME.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, indent=2))
    AUTH_FILE.chmod(0o600)

def _supabase_request(method: str, path: str, body=None, token: str = None) -> dict:
    """Make a request to Supabase REST API."""
    if SUPABASE_URL.startswith("https://YOUR"):
        return {"error": "Supabase not configured. Edit src/pkg_manager.py with your project URL and key."}
    url = SUPABASE_URL + "/rest/v1/" + path
    headers = {
        "apikey":       SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
        "Prefer":       "return=representation",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}

def _verify_token(token: str) -> dict | None:
    """Verify an API token against Supabase. Returns user info or None."""
    result = _supabase_request("GET", "api_tokens?select=user_id,name&token=eq." + token, token=token)
    if isinstance(result, list) and result:
        user_id = result[0]["user_id"]
        profile = _supabase_request("GET", f"profiles?select=username,avatar_url&id=eq.{user_id}", token=token)
        if isinstance(profile, list) and profile:
            return {"user_id": user_id, "username": profile[0].get("username", ""), "token": token}
    return None


# ── Auth commands ─────────────────────────────────────────────────────────────

def cmd_login(token: str = None):
    """Login to KOPPA Registry."""
    if token:
        print("[~] Verifying token…")
        user = _verify_token(token)
        if not user:
            print("[!] Invalid token. Get one from: " + REGISTRY_WEB + "/login.html?cli=1")
            return
        _save_auth(user)
        print(f"[+] Logged in as: {user.get('username') or user.get('user_id')}")
        return

    # Open browser for token
    import webbrowser
    url = REGISTRY_WEB + "/login.html?cli=1"
    print(f"[~] Opening browser: {url}")
    webbrowser.open(url)
    print()
    print("After logging in, copy your CLI token and run:")
    print("  koppa pkg login --token <YOUR_TOKEN>")


def cmd_logout():
    """Logout from KOPPA Registry."""
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
        print("[+] Logged out")
    else:
        print("[!] Not logged in")


def cmd_whoami():
    """Show current user."""
    auth = _load_auth()
    if not auth or not auth.get("token"):
        print("[!] Not logged in.  Run: koppa pkg login")
        return
    user = auth.get("username") or auth.get("user_id", "unknown")
    print(f"Logged in as: {user}")
    print(f"Token:        {auth.get('token', '')[:12]}…")


def cmd_token():
    """Show current API token."""
    auth = _load_auth()
    if not auth or not auth.get("token"):
        print("[!] Not logged in.  Run: koppa pkg login")
        return
    print(f"API Token: {auth['token']}")
    print()
    print("CLI usage:  koppa pkg login --token " + auth['token'])
    print("GitHub CI:  set KOPPA_TOKEN secret, then: koppa pkg publish")


def _security_scan(source: str, filename: str = '') -> dict:
    """Scan KOPPA source for security issues. Returns score, grade, issues list."""
    import re
    issues = []
    score  = 100

    checks = [
        (r'(?:password|passwd)\s*=\s*["\'][^"\']{4,}["\']', 'hardcoded_password',    'high',   20),
        (r'(?:api_key|apikey)\s*=\s*["\'][^"\']{8,}["\']',  'hardcoded_api_key',     'high',   20),
        (r'(?:secret|token)\s*=\s*["\'][^"\']{12,}["\']',   'hardcoded_secret',      'high',   20),
        (r'http\.get\(["\']http://',                          'insecure_http',         'medium', 10),
        (r'os\.exec\s*\([^)]*\+[^)]*\)',                     'exec_injection_risk',   'high',   20),
        (r'hash\.md5\s*\(',                                   'weak_hash_md5',         'low',     5),
        (r'\bcrypt\.rc4\b',                                   'weak_cipher_rc4',       'medium', 10),
    ]
    for pattern, issue_type, severity, penalty in checks:
        if re.search(pattern, source, re.IGNORECASE):
            issues.append({"type": issue_type, "severity": severity,
                           "file": filename})
            score -= penalty

    # Unsafe ops without unsafe block
    unsafe_fns = ['inject.shellcode', 'inject.dll', 'mem.write',
                  'evasion.patch_amsi', 'evasion.patch_etw']
    if not re.search(r'unsafe\s*\{', source):
        for fn in unsafe_fns:
            if fn in source:
                issues.append({"type": "missing_unsafe_block", "severity": "high",
                               "file": filename, "detail": f"{fn} outside unsafe{{}}"})
                score -= 15
                break

    score = max(0, min(100, score))
    grade = 'A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D' if score >= 40 else 'F'
    return {"score": score, "grade": grade, "issues": issues}


def cmd_audit():
    """Audit installed packages for security issues."""
    _ensure_dirs()
    manifest = _installed_manifest()
    if not manifest:
        print("No packages installed. Run: koppa pkg install <name>")
        return

    RESET  = '\033[0m'
    RED    = '\033[31m'
    YELLOW = '\033[33m'
    GREEN  = '\033[32m'
    CYAN   = '\033[36m'
    BOLD   = '\033[1m'
    SEV_COLOR = {'high': RED, 'medium': YELLOW, 'low': CYAN}

    total_issues = 0
    total_files  = 0
    pkg_results  = {}

    for pkg_name in manifest:
        pkg_dir  = PACKAGES_DIR / pkg_name
        kop_files = list(pkg_dir.glob("**/*.kop")) if pkg_dir.exists() else []
        pkg_issues = []

        for kop_file in kop_files:
            try:
                source = kop_file.read_text(encoding='utf-8', errors='replace')
                result = _security_scan(source, kop_file.name)
                if result['issues']:
                    pkg_issues.extend(result['issues'])
                total_files += 1
            except Exception:
                pass

        pkg_results[pkg_name] = pkg_issues
        total_issues += len(pkg_issues)

    print(f"\n{BOLD}KOPPA Security Audit{RESET}")
    print(f"Scanned {total_files} files across {len(manifest)} packages\n")
    print("─" * 54)

    clean = 0
    for pkg_name, issues in pkg_results.items():
        score = max(0, 100 - len(issues) * 15)
        grade = 'A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D' if score >= 40 else 'F'
        grade_color = GREEN if grade in ('A','B') else YELLOW if grade == 'C' else RED

        if not issues:
            print(f"  {GREEN}✓{RESET} {pkg_name:30s} {grade_color}{grade}{RESET} No issues")
            clean += 1
        else:
            print(f"  {RED}✗{RESET} {BOLD}{pkg_name}{RESET}")
            for issue in issues:
                c = SEV_COLOR.get(issue['severity'], '')
                print(f"    {c}[{issue['severity'].upper():6s}]{RESET} {issue['type']}"
                      + (f" ({issue.get('file','')})" if issue.get('file') else ''))

    print("─" * 54)
    if total_issues == 0:
        print(f"\n{GREEN}✓ All {len(manifest)} packages clean — no security issues found{RESET}\n")
    else:
        print(f"\n{RED}✗ {total_issues} issue(s) found in {len(manifest) - clean} package(s){RESET}")
        print(f"  {clean}/{len(manifest)} packages clean\n")
        print("Tip: Use  unsafe {{ }}  blocks for OS-level operations.")
        print("     Avoid hardcoded credentials in package source.\n")


def cmd_publish():
    """Publish the current directory as a KOPPA package."""
    auth = _load_auth()
    if not auth or not auth.get("token"):
        print("[!] Not logged in.  Run: koppa pkg login")
        return

    # Read koppa.json
    mfile = Path("koppa.json")
    if not mfile.exists():
        print("[!] No koppa.json found in current directory.")
        print("    Run: koppa pkg init")
        return

    try:
        pkg = json.loads(mfile.read_text())
    except Exception as e:
        print(f"[!] Failed to parse koppa.json: {e}")
        return

    name    = pkg.get("name", "").strip()
    version = pkg.get("version", "").strip()
    desc    = pkg.get("description", "").strip()
    repo    = pkg.get("repository", pkg.get("url", "")).strip()
    tags    = pkg.get("tags", pkg.get("keywords", []))
    license_= pkg.get("license", "MIT")
    main    = pkg.get("main", "main.kop")

    # Validate
    import re
    if not name:
        print("[!] 'name' is required in koppa.json"); return
    if not re.match(r'^[a-z0-9][a-z0-9\-]{0,63}$', name):
        print("[!] Package name must be lowercase letters, numbers, hyphens"); return
    if not version or not re.match(r'^\d+\.\d+\.\d+$', version):
        print("[!] 'version' must be semver (e.g. 1.0.0)"); return
    if not desc:
        print("[!] 'description' is required in koppa.json"); return
    if not repo:
        print("[!] 'repository' or 'url' (GitHub URL) is required in koppa.json"); return

    token = auth["token"]
    user_id = auth.get("user_id", "")

    print(f"[~] Publishing {name}@{version}…")

    # Upsert package
    payload = {
        "name":           name,
        "description":    desc,
        "author_id":      user_id,
        "author_name":    auth.get("username", ""),
        "latest_version": version,
        "tags":           tags,
        "license":        license_,
        "repo_url":       repo,
        "updated_at":     __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    result = _supabase_request("POST", "packages?on_conflict=name", body=payload, token=token)
    if isinstance(result, dict) and "error" in result:
        print(f"[!] Publish failed: {result['error']}")
        return

    pkg_id = result[0]["id"] if isinstance(result, list) and result else None
    if pkg_id:
        # Insert version record
        _supabase_request("POST", "package_versions", body={
            "package_id":   pkg_id,
            "version":      version,
            "entry_file":   main,
        }, token=token)

    print(f"[+] Published: {name}@{version}")
    print(f"    View at:   {REGISTRY_WEB}/index.html")
    print()
    print("Users can install with:")
    print(f"  koppa pkg install {name}")


def cmd_info(name: str):
    """Show info about a package."""
    registry = _fetch_registry()
    pkg = registry.get("packages", {}).get(name)
    manifest = _installed_manifest()
    installed = manifest.get(name)

    print(f"Package: {name}")
    if pkg:
        print(f"  Registry version : {pkg.get('version', '?')}")
        print(f"  Description      : {pkg.get('description', '')}")
        print(f"  URL              : {pkg.get('url', '')}")
    if installed:
        print(f"  Installed version: {installed.get('version', '?')}")
        print(f"  Location         : {PACKAGES_DIR / name}")
    elif not pkg:
        print("  Not found in registry.")


# ── Package resolution for interpreter ───────────────────────────────────────

def resolve_package_path(name: str) -> Path | None:
    """
    Called by the interpreter's execute_import to look up installed packages.
    Returns path to the package's main .kop file, or None if not found.
    """
    _ensure_dirs()
    pkg_dir = PACKAGES_DIR / name
    if not pkg_dir.exists():
        return None

    # Look for main entry: koppa.json → "main", or <name>.kop, or main.kop, or index.kop
    koppa_json = pkg_dir / "koppa.json"
    if koppa_json.exists():
        meta = json.loads(koppa_json.read_text())
        main = meta.get("main", f"{name}.kop")
        candidate = pkg_dir / main
        if candidate.exists():
            return candidate

    for candidate_name in [f"{name}.kop", "main.kop", "index.kop", f"{name}.apo"]:
        candidate = pkg_dir / candidate_name
        if candidate.exists():
            return candidate

    return None


# ── CLI entry ─────────────────────────────────────────────────────────────────

def main(args: list):
    if not args:
        print("Usage: koppa pkg <command> [args]")
        print()
        print("  install <name|url>         install a package")
        print("  uninstall <name>           remove a package")
        print("  list                       list installed packages")
        print("  search <query>             search registry")
        print("  info <name>                show package info")
        print("  init                       create koppa.json")
        print("  update                     update all packages")
        print()
        print("  login [--token TOKEN]      login to registry")
        print("  logout                     logout")
        print("  whoami                     show current user")
        print("  publish                    publish current package")
        print("  token                      show API token")
        print("  audit                      scan installed packages for security issues")
        return

    sub  = args[0]
    rest = args[1:]

    if sub == "install":
        if not rest: print("Usage: koppa pkg install <name|github-url>")
        else:        cmd_install(rest[0])
    elif sub == "uninstall":
        if not rest: print("Usage: koppa pkg uninstall <name>")
        else:        cmd_uninstall(rest[0])
    elif sub == "list":
        cmd_list()
    elif sub == "search":
        if not rest: print("Usage: koppa pkg search <query>")
        else:        cmd_search(rest[0])
    elif sub == "info":
        if not rest: print("Usage: koppa pkg info <name>")
        else:        cmd_info(rest[0])
    elif sub == "init":
        cmd_init()
    elif sub == "update":
        cmd_update()
    elif sub == "login":
        token = None
        if "--token" in rest:
            idx = rest.index("--token")
            token = rest[idx + 1] if idx + 1 < len(rest) else None
        # Also support KOPPA_TOKEN env var
        if not token:
            token = os.environ.get("KOPPA_TOKEN")
        cmd_login(token)
    elif sub == "logout":
        cmd_logout()
    elif sub == "whoami":
        cmd_whoami()
    elif sub == "publish":
        cmd_publish()
    elif sub == "token":
        cmd_token()
    elif sub == "audit":
        cmd_audit()
    else:
        print(f"Unknown pkg command: {sub}")
