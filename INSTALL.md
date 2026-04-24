# APOLLO Language - Installation & Distribution Guide

## For Users Who Want to Use APOLLO

### Option 1: Quick Install (Copy Folder)

1. **Copy the entire APOLLO folder** to any location (USB drive, cloud sync, network share)
2. **Share the folder** with others via:
   - ZIP the folder and send it
   - Upload to Google Drive/OneDrive and share link
   - Copy to USB drive and share physically
   - Push to GitHub/GitLab

3. **Run from anywhere**:
   ```batch
   cd C:\path\to\APOLLO
   apollo.bat run examples\quick_scan.apollo [target]
   ```

### Option 2: Create Standalone Executable (.exe)

Make APOLLO work without Python installed:

```batch
cd C:\Users\gorku\OneDrive\Desktop\KoppaZZZ\APOLLO

# Install pyinstaller
pip install pyinstaller

# Build standalone executable
pyinstaller --onefile --name apollo src\apollo.py

# Output: dist\apollo.exe
# Share this single file with anyone!
```

Now `apollo.exe` runs on any Windows machine without Python!

### Option 3: Install System-wide

```batch
# Create system folder
mkdir C:\apollo

# Copy files
xcopy /E /Y C:\Users\gorku\OneDrive\Desktop\KoppaZZZ\APOLLO\* C:\apollo\

# Add to PATH (run as admin)
setx /M PATH "%PATH%;C:\apollo"

# Now anyone can run from any command prompt:
apollo run myscript.apollo
```

---

## Distribution Methods

### Method 1: GitHub Repository

```batch
# Initialize git repo
cd C:\Users\gorku\OneDrive\Desktop\KoppaZZZ\APOLLO
git init
git add .
git commit -m "APOLLO Language v1.0"

# Push to GitHub
git remote add origin https://github.com/YOUR_USERNAME/apollo-lang.git
git push -u origin main
```

Now anyone can clone and use:
```bash
git clone https://github.com/YOUR_USERNAME/apollo-lang.git
cd apollo-lang
python src/apollo.py run examples/quick_scan.apollo
```

### Method 2: ZIP Distribution

```batch
# Create distributable ZIP
cd C:\Users\gorku\OneDrive\Desktop\KoppaZZZ
powershell Compress-Archive -Path APOLLO -DestinationPath APOLLO_v1.0.zip

# Share APOLLO_v1.0.zip with anyone
# They just extract and run!
```

### Method 3: PyPI Package (Advanced)

Create `setup.py`:
```python
from setuptools import setup, find_packages

setup(
    name='apollo-pentest',
    version='1.0.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': ['apollo=src.apollo:main'],
    },
    install_requires=[],
)
```

Then:
```batch
pip install .
# or publish to PyPI
pip install twine
twine upload dist/*
# Users can then: pip install apollo-pentest
```

---

## Usage Examples (Share These Scripts)

### 1. Quick Port Scan
```batch
apollo run examples\quick_scan.apollo 192.168.1.1
```

### 2. Web Vulnerability Scan
```batch
apollo run examples\web_fuzzer.apollo http://target.com
```

### 3. Create Your Own Script

Create `myscan.apollo`:
```apollo
import scan, log

fn main(args) {
    let target = args[0] | default("127.0.0.1")
    let ports = [22, 80, 443, 445, 3389]

    log.info("Scanning {target}")

    for port in ports {
        if scan.tcp(target, port) {
            log.info("[+] {port} is open")
        }
    }
}
```

Run:
```batch
apollo run myscan.apollo 192.168.1.100
```

---

## System Requirements

- **Python 3.8+** (for non-.exe version)
- **Windows 10/11** (batch file) or **Linux/Mac** (modify apollo.bat to .sh)
- **Network tools** (optional): nmap, crackmapexec, bloodhound

---

## Sharing with Your Team

### For Pentest Teams

1. **Create shared network location**:
   ```
   \\fileserver\tools\APOLLO\
   ```

2. **Add to team PATH**:
   ```batch
   setx /M PATH "%PATH%;\\fileserver\tools\APOLLO"
   ```

3. **Create team scripts**:
   ```
   \\fileserver\tools\APOLLO\team_scans\
   ├── client_scan.apollo
   ├── server_audit.apollo
   └── webapp_test.apollo
   ```

### For CTF Competitions

Share the ZIP with teammates:
```
APOLLO_CTF.zip
├── src/
├── examples/
├── ctf_scripts/
│   ├── hash_crack.apollo
│   ├── web_enum.apollo
│   └── decoder.apollo
└── apollo.bat
```

---

## Cross-Platform Support

### Linux/Mac Version

Create `apollo.sh`:
```bash
#!/bin/bash
APOLLO_ROOT="$(cd "$(dirname "$0")" && pwd)"

case "$1" in
    run)
        python3 "$APOLLO_ROOT/src/apollo.py" run "${@:2}"
        ;;
    repl)
        python3 "$APOLLO_ROOT/src/apollo.py" repl
        ;;
    *)
        echo "Usage: $0 {run|repl}"
        ;;
esac
```

```bash
chmod +x apollo.sh
./apollo.sh run examples/quick_scan.apollo 127.0.0.1
```

---

## Verification

Test that distribution works:

```batch
# On target machine
apollo.bat run examples\quick_scan.apollo 127.0.0.1
apollo.bat run examples\web_fuzzer.apollo http://example.com
apollo.bat repl
```

---

## Support

For issues or questions:
1. Check `docs/LANGUAGE_SPEC.md`
2. Review `examples/` folder
3. Run `apollo.bat repl` for interactive testing
