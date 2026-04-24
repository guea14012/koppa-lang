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
"""

import json
import shutil
import urllib.request
import urllib.error
import zipfile
import tempfile
import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

KOPPA_HOME    = Path.home() / ".koppa"
PACKAGES_DIR  = KOPPA_HOME / "packages"
REGISTRY_CACHE = KOPPA_HOME / "registry.json"

REGISTRY_URL = (
    "https://raw.githubusercontent.com/YOUR_USERNAME/koppa-registry/main/index.json"
)

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
        print("  install <name|url>   — install a package")
        print("  uninstall <name>     — remove a package")
        print("  list                 — list installed")
        print("  search <query>       — search registry")
        print("  info <name>          — show package info")
        print("  init                 — create koppa.json")
        print("  update               — update all packages")
        return

    sub = args[0]
    rest = args[1:]

    if sub == "install":
        if not rest:
            print("Usage: koppa pkg install <name|github-url>")
        else:
            cmd_install(rest[0])
    elif sub == "uninstall":
        if not rest:
            print("Usage: koppa pkg uninstall <name>")
        else:
            cmd_uninstall(rest[0])
    elif sub == "list":
        cmd_list()
    elif sub == "search":
        if not rest:
            print("Usage: koppa pkg search <query>")
        else:
            cmd_search(rest[0])
    elif sub == "info":
        if not rest:
            print("Usage: koppa pkg info <name>")
        else:
            cmd_info(rest[0])
    elif sub == "init":
        cmd_init()
    elif sub == "update":
        cmd_update()
    else:
        print(f"Unknown pkg command: {sub}")
