# KOPPA Language Specification v2.0

## Overview

KOPPA is a domain-specific language for security professionals. It combines readable Python-like syntax with built-in security primitives, pipeline operators, and async execution.

---

## 1. Syntax Basics

### Comments
```koppa
# This is a comment
```

### Variables
```koppa
let name = "Alice"        # immutable
var count = 0             # mutable
const MAX = 100           # constant
```

### String Interpolation
```koppa
let host = "192.168.1.1"
log.info("Scanning {host}...")        # → "Scanning 192.168.1.1..."
log.info("{host} port {port}")        # nested vars
```

---

## 2. Types

| Type | Example |
|------|---------|
| `string` | `"hello"` |
| `int` | `42` |
| `float` | `3.14` |
| `bool` | `true` / `false` |
| `array` | `[1, 2, 3]` |
| `dict` | `{key: value}` |
| `null` | `null` |

---

## 3. Functions

```koppa
fn greet(name) {
    return "Hello {name}"
}

fn scan(host, port) -> Result {
    if net.tcp_connect(host, port) {
        return Ok(port)
    }
    return Err("closed")
}
```

### Async Functions
```koppa
async fn fetch_all(targets) {
    for target in targets {
        let result = http.get(target)
        emit result
    }
}
```

---

## 4. Control Flow

### If / Elif / Else
```koppa
if score > 90 {
    log.success("Critical")
} elif score > 50 {
    log.warn("Medium")
} else {
    log.info("Low")
}
```

### For Loop
```koppa
for port in [22, 80, 443] {
    log.info("Port: {port}")
}
```

### While Loop
```koppa
var i = 0
while i < 10 {
    i = i + 1
}
```

### Match (Pattern Matching)
```koppa
match service {
    "http"  => http.scan(target),
    "ssh"   => ssh.audit(target),
    "smb"   => smb.enum(target),
    _       => log.info("Unknown: {service}")
}
```

---

## 5. Error Handling

### Try / Catch
```koppa
try {
    let data = fs.read("/etc/shadow")
    log.info(data)
} catch(err) {
    log.error("Failed: {err}")
}
```

### Throw
```koppa
fn divide(a, b) {
    if b == 0 {
        throw "Division by zero"
    }
    return a / b
}
```

### Result Type
```koppa
fn safe_scan(host, port) -> Result {
    try {
        let open = scan.tcp(host, port)
        return Ok(open)
    } catch(e) {
        return Err(e)
    }
}

match safe_scan("target.com", 80) {
    Ok(result) => log.success("Open: {result}"),
    Err(e)     => log.error("Error: {e}")
}
```

---

## 6. Pipeline Operator

```koppa
target
    |> recon.dns_resolve()
    |> scan.tcp([80, 443])
    |> parse.html_links()
    |> report.save("output.json")
```

---

## 7. Async & Parallel

```koppa
# Run function concurrently
async fn scan_port(host, port) {
    return scan.tcp(host, port)
}

# Parallel block — all statements run concurrently
parallel {
    scan_port("target.com", 80)
    scan_port("target.com", 443)
    scan_port("target.com", 8080)
}
```

---

## 8. Modules

### Import
```koppa
import log                          # single
import log, scan, http, crypto      # multiple
```

### Available Built-in Modules

| Category | Modules |
|----------|---------|
| Network | `scan` `net` `dns` `ssl` `http` `ftp` `smtp` |
| Security | `fuzz` `brute` `parse` `report` `exploit` |
| Crypto | `hash` `encode` `crypto` `jwt` |
| Core | `str` `list` `math` `rand` `regex` `json` |
| System | `fs` `os` `time` `fmt` `color` `io` |
| Recon | `recon` `enum` |

---

## 9. Module API Reference

### log
```koppa
log.info("message")
log.warn("message")
log.error("message")
log.success("message")
log.debug("message")
```

### scan
```koppa
scan.tcp(host, port)           # → bool
scan.tcp(host, port, timeout)  # → bool
scan.service(port)             # → string ("http", "ssh", ...)
```

### net
```koppa
net.tcp_connect(host, port)    # → bool
net.tcp_banner(host, port)     # → string
net.ping(host)                 # → dict {success, output}
net.geo_ip(ip)                 # → dict {country, city, isp}
net.local_ip()                 # → string
net.public_ip()                # → string
net.port_range(host, 1, 1024)  # → array of open ports
net.cidr_hosts("10.0.0.0/24") # → array of IPs
```

### dns
```koppa
dns.resolve(domain)            # → string (IP)
dns.resolve_all(domain)        # → array
dns.reverse(ip)                # → string
dns.mx(domain)                 # → array
dns.txt(domain)                # → array
dns.zone_transfer(domain, ns)  # → array
```

### http
```koppa
http.get(url)                  # → {status, headers, body}
http.post(url, data)           # → {status, headers, body}
```

### hash
```koppa
hash.md5(text)                 # → string
hash.sha256(text)              # → string
hash.sha512(text)              # → string
hash.ntlm(password)            # → string
hash.identify(hash_str)        # → string ("MD5 or NTLM", ...)
hash.crack(hash, wordlist)     # → {cracked, password}
hash.file(path)                # → {md5, sha1, sha256}
```

### encode
```koppa
encode.b64_encode(text)        # → string
encode.b64_decode(text)        # → string
encode.hex_encode(text)        # → string
encode.url_encode(text)        # → string
encode.xor(text, key)          # → string
encode.rot13(text)             # → string
encode.detect(text)            # → string ("base64", "hex", ...)
```

### jwt
```koppa
jwt.decode(token)              # → {header, payload, signature}
jwt.verify(token, secret)      # → bool
jwt.none_alg(token)            # → string (forged token)
jwt.crack(token, wordlist)     # → {cracked, secret}
jwt.forge(payload, secret)     # → string
jwt.is_expired(token)          # → bool
```

### fuzz
```koppa
fuzz.dirs(url, wordlist)       # → array of {url, status}
fuzz.params(url, wordlist)     # → array
fuzz.sqli_quick(url, param)    # → array of findings
fuzz.xss_quick(url, param)     # → array of findings
fuzz.payloads_sqli()           # → array of payload strings
fuzz.payloads_xss()            # → array of payload strings
fuzz.payloads_lfi()            # → array
```

### parse
```koppa
parse.html_links(html)         # → array of URLs
parse.html_forms(html)         # → array of {action, method, inputs}
parse.html_title(html)         # → string
parse.extract_emails(text)     # → array
parse.extract_ips(text)        # → array
parse.extract_secrets(text)    # → array of {type, value}
parse.url_parts(url)           # → {scheme, host, path, query}
```

### report
```koppa
report.finding(title, severity, description)   # → dict
report.html(findings, title)                   # → string (HTML)
report.markdown(findings, title)               # → string
report.save(findings, path, format)            # → string (path)
report.terminal(findings)                      # → string
report.summary(findings)                       # → {total, by_severity}
```

### str
```koppa
str.upper(s)                   # → string
str.lower(s)                   # → string
str.split(s, sep)              # → array
str.join(sep, array)           # → string
str.contains(s, sub)           # → bool
str.replace(s, old, new)       # → string
str.strip(s)                   # → string
str.len(s)                     # → int
str.startswith(s, prefix)      # → bool
str.endswith(s, suffix)        # → bool
str.is_digit(s)                # → bool
str.truncate(s, n)             # → string
```

### fs
```koppa
fs.read(path)                  # → string
fs.write(path, content)        # → null
fs.append(path, content)       # → null
fs.exists(path)                # → bool
fs.list(path)                  # → array
fs.lines(path)                 # → array of strings
fs.read_json(path)             # → dict
fs.write_json(path, obj)       # → null
fs.size(path)                  # → int (bytes)
fs.glob(path, pattern)         # → array
```

### os
```koppa
os.exec(command)               # → {stdout, stderr, code}
os.env(key)                    # → string
os.hostname()                  # → string
os.platform()                  # → string
os.is_root()                   # → bool
```

### time
```koppa
time.now()                     # → string (datetime)
time.timestamp()               # → int (unix)
time.sleep(seconds)            # → null
time.date()                    # → string "YYYY-MM-DD"
time.clock()                   # → string "HH:MM:SS"
```

### ssl
```koppa
ssl.get_cert(host, port)       # → dict (certificate)
ssl.verify(host, port)         # → bool
ssl.fingerprint(host, port)    # → string (SHA256)
ssl.expiry(host, port)         # → string
ssl.issuer(host, port)         # → string
ssl.hsts(host)                 # → bool
ssl.is_expired(host, port)     # → bool
ssl.san(host, port)            # → array of domains
```

---

## 10. Package Manager

```bash
koppa pkg install <name>       # install from registry
koppa pkg install <github-url> # install from GitHub
koppa pkg uninstall <name>     # remove
koppa pkg list                 # list installed
koppa pkg search <query>       # search registry
koppa pkg info <name>          # show details
koppa pkg init                 # create koppa.json
koppa pkg update               # update all
```

---

## 11. CLI Reference

```bash
koppa run script.kop           # run script (interpreter)
koppa run --vm script.kop      # run with bytecode VM
koppa compile script.kop       # compile to .kpc bytecode
koppa repl                     # interactive REPL
koppa lex script.kop           # show token stream
koppa parse script.kop         # show AST (JSON)
koppa disasm script.kop        # disassemble bytecode
koppa version                  # version info
koppa -c 'code'                # run inline code
```

---

## 12. REPL Commands

```
koppa> help       — show commands
koppa> modules    — list available modules
koppa> exit       — quit
koppa> clear      — clear screen
```

---

*KOPPA v2.0.1 — Built for security professionals*
