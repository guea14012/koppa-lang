#!/usr/bin/env python3
"""
KOPPA Build Script
Creates a distributable ZIP + optionally a standalone .exe via PyInstaller.

Usage:
    python BUILD_KOPPA.py           # build ZIP + pip-installable package
    python BUILD_KOPPA.py --exe     # also build standalone koppa.exe
    python BUILD_KOPPA.py --clean   # clean DIST/ and exit
"""

import os
import sys
import shutil
import zipfile
import argparse
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DIST_DIR     = PROJECT_ROOT / "DIST"
VERSION      = "2.0.0"


def clean():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
        print(f"[OK] Cleaned {DIST_DIR}")


def build_dist():
    print(f"\nBuilding KOPPA v{VERSION}...")

    # ── Layout ───────────────────────────────────────────────
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    (DIST_DIR / "src").mkdir(exist_ok=True)
    (DIST_DIR / "stdlib").mkdir(exist_ok=True)
    (DIST_DIR / "examples").mkdir(exist_ok=True)
    (DIST_DIR / "docs").mkdir(exist_ok=True)

    # ── Source files ─────────────────────────────────────────
    src_dir = PROJECT_ROOT / "src"
    for f in src_dir.glob("*.py"):
        shutil.copy2(f, DIST_DIR / "src" / f.name)
    # Copy deno runtime if present
    deno_rt = src_dir / "deno_runtime.ts"
    if deno_rt.exists():
        shutil.copy2(deno_rt, DIST_DIR / "src" / "deno_runtime.ts")
    print(f"[OK] Source files: {len(list((DIST_DIR / 'src').iterdir()))} files")

    # ── Stdlib ───────────────────────────────────────────────
    stdlib_src = PROJECT_ROOT / "stdlib"
    if stdlib_src.exists():
        for f in stdlib_src.iterdir():
            if f.is_file():
                dest = f.name.replace(".apo", ".kop")
                shutil.copy2(f, DIST_DIR / "stdlib" / dest)
        print(f"[OK] Stdlib: {len(list((DIST_DIR / 'stdlib').iterdir()))} files")

    # ── Examples ─────────────────────────────────────────────
    examples_src = PROJECT_ROOT / "examples"
    if examples_src.exists():
        for f in examples_src.glob("*.kop"):
            shutil.copy2(f, DIST_DIR / "examples" / f.name)
        print(f"[OK] Examples: {len(list((DIST_DIR / 'examples').iterdir()))} files")

    # ── Docs ─────────────────────────────────────────────────
    for doc in ["README.md", "INSTALL.md"]:
        src = PROJECT_ROOT / doc
        if src.exists():
            shutil.copy2(src, DIST_DIR / doc)

    # ── Logo ─────────────────────────────────────────────────
    logo = PROJECT_ROOT / "koppa logo.png"
    if logo.exists():
        shutil.copy2(logo, DIST_DIR / "koppa logo.png")

    # ── Launchers ────────────────────────────────────────────
    shutil.copy2(PROJECT_ROOT / "koppa.bat", DIST_DIR / "koppa.bat")
    shutil.copy2(PROJECT_ROOT / "koppa.sh",  DIST_DIR / "koppa.sh")
    shutil.copy2(PROJECT_ROOT / "install.bat", DIST_DIR / "install.bat")
    shutil.copy2(PROJECT_ROOT / "install.sh",  DIST_DIR / "install.sh")

    # ── setup.py / pyproject.toml for pip install ────────────
    shutil.copy2(PROJECT_ROOT / "setup.py",       DIST_DIR / "setup.py")
    shutil.copy2(PROJECT_ROOT / "pyproject.toml", DIST_DIR / "pyproject.toml")

    # ── Tests ─────────────────────────────────────────────────
    tests_src = PROJECT_ROOT / "tests"
    if tests_src.exists():
        (DIST_DIR / "tests").mkdir(exist_ok=True)
        for f in tests_src.glob("*.py"):
            shutil.copy2(f, DIST_DIR / "tests" / f.name)

    # ── CI / CD workflows ────────────────────────────────────
    workflows_src = PROJECT_ROOT / ".github" / "workflows"
    if workflows_src.exists():
        (DIST_DIR / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        for f in workflows_src.glob("*.yml"):
            shutil.copy2(f, DIST_DIR / ".github" / "workflows" / f.name)

    # ── Homebrew formula ─────────────────────────────────────
    formula_src = PROJECT_ROOT / "Formula"
    if formula_src.exists():
        (DIST_DIR / "Formula").mkdir(exist_ok=True)
        for f in formula_src.glob("*.rb"):
            shutil.copy2(f, DIST_DIR / "Formula" / f.name)

    # ── winget manifest ──────────────────────────────────────
    winget_src = PROJECT_ROOT / "winget"
    if winget_src.exists():
        (DIST_DIR / "winget").mkdir(exist_ok=True)
        for f in winget_src.glob("*.yaml"):
            shutil.copy2(f, DIST_DIR / "winget" / f.name)

    # ── Scoop manifest ───────────────────────────────────────
    scoop_src = PROJECT_ROOT / "scoop"
    if scoop_src.exists():
        (DIST_DIR / "scoop").mkdir(exist_ok=True)
        for f in scoop_src.glob("*.json"):
            shutil.copy2(f, DIST_DIR / "scoop" / f.name)

    # ── .deb build script ────────────────────────────────────
    pkg_src = PROJECT_ROOT / "pkg"
    if pkg_src.exists():
        (DIST_DIR / "pkg").mkdir(exist_ok=True)
        for f in pkg_src.iterdir():
            if f.is_file():
                shutil.copy2(f, DIST_DIR / "pkg" / f.name)

    # ── Web installer ────────────────────────────────────────
    web_installer = PROJECT_ROOT / "install-web.sh"
    if web_installer.exists():
        shutil.copy2(web_installer, DIST_DIR / "install-web.sh")

    # ── Landing page ─────────────────────────────────────────
    www_src = PROJECT_ROOT / "www"
    if www_src.exists():
        (DIST_DIR / "www").mkdir(exist_ok=True)
        for f in www_src.iterdir():
            if f.is_file():
                shutil.copy2(f, DIST_DIR / "www" / f.name)

    print(f"[OK] Launchers, setup files, CI/CD, and package manifests copied")

    # ── ZIP package ──────────────────────────────────────────
    zip_path = PROJECT_ROOT / f"KOPPA_v{VERSION}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(DIST_DIR):
            for fname in files:
                fpath = Path(root) / fname
                arcname = Path("KOPPA") / fpath.relative_to(DIST_DIR)
                zf.write(fpath, arcname)
    print(f"[OK] ZIP package: {zip_path}  ({zip_path.stat().st_size // 1024} KB)")

    return DIST_DIR


def build_exe():
    """Build standalone koppa.exe using PyInstaller"""
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("[!] PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    entry = PROJECT_ROOT / "src" / "koppa.py"
    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", "koppa",
            "--distpath", str(DIST_DIR / "bin"),
            "--workpath", str(DIST_DIR / "_build"),
            "--specpath", str(DIST_DIR / "_build"),
            str(entry),
        ],
        cwd=str(PROJECT_ROOT / "src"),
    )
    if result.returncode == 0:
        print(f"[OK] Executable: {DIST_DIR / 'bin' / 'koppa.exe'}")
    else:
        print("[WARN] PyInstaller failed — ZIP package still works")


def main():
    parser = argparse.ArgumentParser(description="KOPPA build tool")
    parser.add_argument("--exe",   action="store_true", help="also build standalone .exe")
    parser.add_argument("--clean", action="store_true", help="clean DIST/ only")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    clean()
    dist = build_dist()

    if args.exe:
        build_exe()

    print(f"\n{'='*50}")
    print(f"  Build complete!")
    print(f"  Distribution : {dist}")
    print(f"  ZIP          : {PROJECT_ROOT}/KOPPA_v{VERSION}.zip")
    print(f"{'='*50}")
    print(f"\nShare the ZIP or run  pip install {dist}  to install.")
    print(f"Or run install.bat / install.sh from the DIST folder.")


if __name__ == "__main__":
    main()
