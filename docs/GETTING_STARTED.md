# Getting Started with KOPPA

## Installation

```bash
pip install koppa-lang
```

Or from source:
```bash
git clone https://github.com/guea14012/koppa-lang.git
cd koppa-lang
pip install .
```

Verify:
```bash
koppa version
```

---

## Your First Script

Create `hello.kop`:
```koppa
import log

fn main() {
    let name = "KOPPA"
    log.info("Hello from {name}!")
    log.success("Ready to hack.")
}
```

Run:
```bash
koppa run hello.kop
```

---

## Port Scanner

```koppa
import scan, log

let target = "127.0.0.1"
let ports  = [22, 80, 443, 3306, 5432, 8080]

log.info("Scanning {target}...")

for port in ports {
    if scan.tcp(target, port) {
        let svc = scan.service(port)
        log.success("[+] {port}/tcp open — {svc}")
    }
}
```

---

## Hash & Encode

```koppa
import hash, encode, log

let secret = "password123"

log.info("MD5    : {hash.md5(secret)}")
log.info("SHA256 : {hash.sha256(secret)}")
log.info("NTLM   : {hash.ntlm(secret)}")
log.info("Base64 : {encode.b64_encode(secret)}")
log.info("Detect : {encode.detect('SGVsbG8=')}")
```

---

## HTTP & Web

```koppa
import http, parse, log

let url = "https://example.com"
let resp = http.get(url)

log.info("Status : {resp.status}")
log.info("Title  : {parse.html_title(resp.body)}")

let links = parse.html_links(resp.body)
for link in links {
    log.info("Link: {link}")
}
```

---

## Error Handling

```koppa
import fs, log

try {
    let content = fs.read("/etc/shadow")
    log.info(content)
} catch(err) {
    log.error("Permission denied: {err}")
}
```

---

## DNS Recon

```koppa
import dns, log

let domain = "example.com"

let ip  = dns.resolve(domain)
let rev = dns.reverse(ip)
let mx  = dns.mx(domain)
let txt = dns.txt(domain)

log.info("{domain} → {ip}")
log.info("Reverse : {rev}")
log.info("MX      : {mx}")
log.info("TXT     : {txt}")
```

---

## Web Fuzzing

```koppa
import fuzz, log, report

let url  = "https://target.com"
let list = ["admin", "login", "api", "backup", "config"]

let dirs = fuzz.dirs(url, list)
for hit in dirs {
    log.success("Found: {hit}")
}

let sqli = fuzz.sqli_quick(url + "/search", "q")
for vuln in sqli {
    log.warn("SQLi: {vuln}")
}
```

---

## Generate Report

```koppa
import report, log

let findings = [
    report.finding("SQL Injection", "Critical", "Found in /login?id= parameter"),
    report.finding("XSS", "High", "Reflected XSS in search param"),
    report.finding("Directory Listing", "Low", "/backup/ exposed"),
]

let summary = report.summary(findings)
log.info("Total: {summary}")

report.save(findings, "report.html", "html")
log.success("Report saved to report.html")
```

---

## Install Packages

```bash
koppa pkg search scanner
koppa pkg install koppa-nmap
koppa pkg install koppa-sqli
koppa pkg list
```

---

## Interactive REPL

```bash
koppa repl
```

```
koppa> import hash
koppa> hash.md5("test")
= "098f6bcd4621d373cade4e832627b4f6"
koppa> modules
```

---

## Next Steps

- [Language Specification](LANGUAGE_SPEC.md) — full syntax reference
- [Package Registry](https://guea14012.github.io/koppa-registry-/) — community modules
- [GitHub](https://github.com/guea14012/koppa-lang) — source code & issues
