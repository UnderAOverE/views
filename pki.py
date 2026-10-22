#!/usr/bin/env python3
"""
pkicheck.py - PKI / OCSP troubleshooting tool for production support.

Takes a certificate (file, or host:port to grab it live), extracts the pieces
that matter for revocation checking (issuer, OCSP URL, CRL URL, expiry) and
then actually tests each dependency with timing.

Usage:
  pkicheck.py cert.pem                          text report (default)
  pkicheck.py host.corp:443                     fetch the cert from a live TLS endpoint
  pkicheck.py cert.pem -i issuer.pem            supply the issuer (skips AIA download)
  pkicheck.py cert.pem -o http://localhost:8080/ejbca/publicweb/status/ocsp
                                                test an extra OCSP URL (repeatable)
  pkicheck.py cert.pem --json                   JSON to stdout
  pkicheck.py cert.pem --json -O report.json    JSON to a file
  pkicheck.py cert.pem --html -O report.html    HTML report to a file
  pkicheck.py cert.pem --no-crl -t 5            skip CRL, 5 s timeout
  pkicheck.py cert.pem --servers pki.json       also test every VA listed in pki.json
  pkicheck.py cert.pem --servers pki.json --ignore-aia
                                                test ONLY the servers in pki.json, not the
                                                OCSP URL printed in the cert

Servers file (JSON). Only "va_servers" is required:
  {
    "va_servers": ["pkivamwp01", "pkivamwp02"],
    "ocsp_scheme": "http",                                  default http
    "ocsp_port": 8080,                                      default 8080
    "ocsp_path": "/ejbca/publicweb/status/ocsp",            default (EJBCA)
    "lb_url": "http://ngocsp.citi.com/ocsp",                optional: the load-balanced name
    "issuers": ["/opt/pki/CitiDeviceCA2G2.pem", "..."]     optional: local CA certs; the one
                                                            that signed the leaf is used, so
                                                            no AIA download is needed
  }
  An entry in va_servers may also be a full URL, or "host:port".

Exit code: 0 all OK, 1 warnings, 2 failures.
Needs: Python 3.6+ and the openssl command. No pip packages.
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

SLOW_MS = 1000       # OCSP/CRL slower than this = WARN
BIG_CRL_KB = 2048    # CRL bigger than this = WARN
EXPIRY_WARN_DAYS = 30
VERSION = "1.0"


# ----------------------------------------------------------------- helpers
class Report:
    """Collects findings and renders them as text / json / html."""

    def __init__(self):
        self.started = dt.datetime.now(dt.timezone.utc)
        self.host = socket.gethostname()
        self.certificate = {}
        self.issuer = {}
        self.ocsp = []
        self.crl = []
        self.findings = []           # {"level": ok|warn|fail, "section": ..., "msg": ...}
        self.servers_file = None

    # findings
    def ok(self, section, msg):   self.findings.append({"level": "ok",   "section": section, "msg": msg})
    def warn(self, section, msg): self.findings.append({"level": "warn", "section": section, "msg": msg})
    def fail(self, section, msg): self.findings.append({"level": "fail", "section": section, "msg": msg})

    def count(self, level):
        return sum(1 for f in self.findings if f["level"] == level)

    @property
    def exit_code(self):
        if self.count("fail"):
            return 2
        if self.count("warn"):
            return 1
        return 0

    @property
    def verdict(self):
        return {0: "HEALTHY", 1: "WARNINGS", 2: "FAILURES"}[self.exit_code]

    def entry_findings(self, entries):
        """Attach to each ocsp/crl entry the findings recorded while it ran."""
        out = []
        for k, e in enumerate(entries):
            f0 = e.get("_f0", 0)
            f1 = entries[k + 1].get("_f0", len(self.findings)) if k + 1 < len(entries) else None
            sec = "ocsp" if entries is self.ocsp else "crl"
            fs = [f for f in self.findings[f0:f1] if f["section"] == sec]
            d = {kk: vv for kk, vv in e.items() if not kk.startswith("_")}
            d["findings"] = fs
            out.append(d)
        return out

    def to_dict(self):
        finished = dt.datetime.now(dt.timezone.utc)
        return {
            "tool": "pkicheck", "version": VERSION,
            "run_at": self.started.isoformat(timespec="milliseconds"),
            "run_at_local": self.started.astimezone().isoformat(timespec="seconds"),
            "finished_at": finished.isoformat(timespec="milliseconds"),
            "duration_ms": int((finished - self.started).total_seconds() * 1000),
            "run_from": self.host,
            "verdict": self.verdict, "exit_code": self.exit_code,
            "summary": {"ok": self.count("ok"), "warn": self.count("warn"), "fail": self.count("fail")},
            "servers_file": self.servers_file,
            "certificate": self.certificate,
            "issuer": self.issuer,
            "ocsp": self.entry_findings(self.ocsp),
            "crl": self.entry_findings(self.crl),
            "findings": self.findings,
        }


def run(cmd, stdin=None, timeout=30):
    """Run a command; return (rc, stdout+stderr)."""
    try:
        p = subprocess.run(cmd, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except FileNotFoundError:
        return 127, "command not found: " + cmd[0]


def now_ms():
    return int(time.time() * 1000)


def to_pem(path):
    """Return PEM text of a cert file that may be PEM or DER."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if b"BEGIN CERTIFICATE" in raw:
        rc, out = run(["openssl", "x509", "-in", path])
    else:
        rc, out = run(["openssl", "x509", "-inform", "DER", "-in", path])
    if rc != 0 or "BEGIN CERTIFICATE" not in out:
        return None
    return out


def write_tmp(workdir, name, text):
    p = os.path.join(workdir, name)
    with open(p, "w") as fh:
        fh.write(text)
    return p


def parse_openssl_date(s):
    """'Oct 21 13:31:12 2026 GMT' -> aware datetime."""
    try:
        return dt.datetime.strptime(s.strip(), "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def proxy_for(url):
    """Which proxy (if any) the OS environment would route this URL through."""
    try:
        proxies = urllib.request.getproxies()
        scheme = urllib.parse.urlsplit(url).scheme
        host = urllib.parse.urlsplit(url).hostname or ""
        if urllib.request.proxy_bypass(host):
            return None
        return proxies.get(scheme)
    except Exception:  # noqa: BLE001
        return None


def network_probe(url, timeout):
    """Resolve the host and open a TCP socket, timing each step, so DNS and
    connect problems are reported separately from HTTP / OCSP problems."""
    u = urllib.parse.urlsplit(url)
    host = u.hostname or ""
    port = u.port or (443 if u.scheme == "https" else 80)
    n = {"host": host, "port": port, "proxy": proxy_for(url),
         "dns_ms": None, "addresses": [], "dns_error": None,
         "tcp_ms": None, "tcp_error": None, "ok": False}
    t0 = now_ms()
    try:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        n["dns_ms"] = now_ms() - t0
        n["addresses"] = sorted({i[4][0] for i in infos})
    except socket.gaierror as e:
        n["dns_ms"] = now_ms() - t0
        n["dns_error"] = "DNS: %s (errno %s)" % (e.strerror or e, e.errno)
        return n
    except Exception as e:  # noqa: BLE001
        n["dns_ms"] = now_ms() - t0
        n["dns_error"] = "DNS: %s" % e
        return n
    if n["proxy"]:
        # with a proxy the client never connects to the host directly
        n["tcp_error"] = "not tested (requests go via proxy %s)" % n["proxy"]
        n["ok"] = True
        return n
    t0 = now_ms()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        n["tcp_ms"] = now_ms() - t0
        n["ok"] = True
    except socket.timeout:
        n["tcp_ms"] = now_ms() - t0
        n["tcp_error"] = "TCP connect timed out after %ds (firewall drop or host down)" % timeout
    except OSError as e:
        n["tcp_ms"] = now_ms() - t0
        n["tcp_error"] = "TCP connect: %s (errno %s)" % (e.strerror or e, e.errno)
    return n


def describe_exception(e):
    """Turn a urllib/socket exception into a one-line, layer-labelled message."""
    if isinstance(e, urllib.error.HTTPError):
        return "HTTP %d %s" % (e.code, e.reason)
    if isinstance(e, urllib.error.URLError):
        r = e.reason
        if isinstance(r, socket.gaierror):
            return "DNS: %s (errno %s)" % (r.strerror or r, r.errno)
        if isinstance(r, socket.timeout):
            return "timed out"
        if isinstance(r, ssl.SSLError):
            return "TLS: %s" % (r.reason or r)
        if isinstance(r, OSError):
            return "OS: %s (errno %s)" % (r.strerror or r, r.errno)
        return "URL error: %s" % r
    if isinstance(e, socket.timeout):
        return "timed out"
    if isinstance(e, ssl.SSLError):
        return "TLS: %s" % (e.reason or e)
    if isinstance(e, OSError):
        return "OS: %s (errno %s)" % (e.strerror or e, e.errno)
    return "%s: %s" % (type(e).__name__, e)


def http_get(url, timeout):
    """Download url; return (status, bytes, ms, error, info)."""
    info = {"proxy": proxy_for(url), "http_status": None, "server": None, "content_type": None, "raw_error": None}
    t0 = now_ms()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pkicheck/" + VERSION})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            info["http_status"] = r.status
            info["server"] = r.headers.get("Server")
            info["content_type"] = r.headers.get("Content-Type")
            return r.status, data, now_ms() - t0, None, info
    except urllib.error.HTTPError as e:
        info["http_status"] = e.code
        info["server"] = e.headers.get("Server") if e.headers else None
        info["raw_error"] = str(e)
        return e.code, b"", now_ms() - t0, describe_exception(e), info
    except Exception as e:  # noqa: BLE001
        info["raw_error"] = repr(e)
        return None, b"", now_ms() - t0, describe_exception(e), info


def load_servers_file(path):
    """Read the servers JSON; return (responders, issuer_files, lb_url).
    responders = [{"label": ..., "url": ...}, ...]"""
    with open(path) as fh:
        cfg = json.load(fh)
    if not isinstance(cfg, dict) or not isinstance(cfg.get("va_servers"), list):
        raise ValueError('%s must be a JSON object with a "va_servers" list' % path)
    scheme = cfg.get("ocsp_scheme", "http")
    port = int(cfg.get("ocsp_port", 8080))
    ocsp_path = cfg.get("ocsp_path", "/ejbca/publicweb/status/ocsp")
    if not ocsp_path.startswith("/"):
        ocsp_path = "/" + ocsp_path
    responders = []
    for s in cfg["va_servers"]:
        s = str(s).strip()
        if not s:
            continue
        if "://" in s:
            url = s
            label = urllib.parse.urlsplit(s).hostname or s
        elif ":" in s:
            host, _, p = s.partition(":")
            url = "%s://%s:%s%s" % (scheme, host, p, ocsp_path)
            label = s
        else:
            url = "%s://%s:%d%s" % (scheme, s, port, ocsp_path)
            label = s
        responders.append({"label": "VA " + label, "url": url})
    if cfg.get("lb_url"):
        responders.insert(0, {"label": "load balancer", "url": cfg["lb_url"]})
    issuers = [str(p) for p in cfg.get("issuers", []) if p]
    base = os.path.dirname(os.path.abspath(path))
    issuers = [p if os.path.isabs(p) else os.path.join(base, p) for p in issuers]
    return responders, issuers, cfg.get("lb_url")


def pick_issuer_from_files(rep, leaf, files):
    """Return the first file whose certificate verifies the leaf, or None."""
    for f in files:
        if not os.path.isfile(f):
            rep.warn("issuer", "issuer file listed in servers file not found: %s" % f)
            continue
        pem = to_pem(f)
        if not pem:
            rep.warn("issuer", "issuer file is not a certificate: %s" % f)
            continue
        rc1, _ = run(["openssl", "verify", "-partial_chain", "-CAfile", f, leaf])
        rc2, _ = run(["openssl", "verify", "-no_check_time", "-partial_chain", "-CAfile", f, leaf])
        if rc1 == 0 or rc2 == 0:
            return f
    return None


# ------------------------------------------------------------- the checks
def get_certificate(rep, target, timeout, workdir):
    """Load the leaf cert from a file or a TLS endpoint. Returns (leaf_pem_path, chain_issuer_pem_or_None)."""
    if os.path.isfile(target):
        pem = to_pem(target)
        if not pem:
            rep.fail("certificate", "cannot parse %s as PEM or DER" % target)
            return None, None
        rep.certificate["source"] = target
        return write_tmp(workdir, "leaf.pem", pem), None

    host, _, port = target.partition(":")
    port = int(port) if port else 443
    net = network_probe("https://%s:%d/" % (host, port), timeout)
    net["proxy"] = None  # s_client always connects directly
    rep.certificate["network"] = net
    if net["dns_error"]:
        rep.fail("certificate", "%s: %s" % (host, net["dns_error"]))
        return None, None
    if net["tcp_error"]:
        rep.fail("certificate", "%s:%d - %s" % (host, port, net["tcp_error"]))
        return None, None
    t0 = now_ms()
    rc, out = run(["openssl", "s_client", "-connect", "%s:%d" % (host, port), "-servername", host,
                   "-showcerts"], stdin=b"", timeout=timeout)
    ms = now_ms() - t0
    certs = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", out, re.S)
    if rc == 124 or not certs:
        errline = next((l for l in out.split("\n") if re.search(r"error|alert|refused|reset", l, re.I)), "").strip()
        rep.certificate["raw_error"] = out.strip()[:2000]
        rep.fail("certificate", "TCP connected to %s:%d in %s ms but the TLS handshake failed after %d ms%s"
                 % (host, port, net["tcp_ms"], ms, " - " + errline[:160] if errline else ""))
        return None, None
    rep.certificate["source"] = "TLS handshake with %s:%d" % (host, port)
    rep.certificate["handshake_ms"] = ms
    rep.certificate["chain_length"] = len(certs)
    leaf = write_tmp(workdir, "leaf.pem", certs[0] + "\n")
    issuer = write_tmp(workdir, "chain-issuer.pem", certs[1] + "\n") if len(certs) > 1 else None
    rep.ok("certificate", "TLS handshake with %s:%d in %d ms, %d cert(s) in chain" % (host, port, ms, len(certs)))
    return leaf, issuer


def x509(leaf, *args):
    rc, out = run(["openssl", "x509", "-in", leaf, "-noout"] + list(args))
    return out.strip() if rc == 0 else ""


def describe_certificate(rep, leaf, ignore_aia=False):
    c = rep.certificate
    c["aia_ignored"] = ignore_aia
    c["subject"] = re.sub(r"^subject=\s*", "", x509(leaf, "-subject"))
    c["issuer_dn"] = re.sub(r"^issuer=\s*", "", x509(leaf, "-issuer"))
    c["serial"] = x509(leaf, "-serial").replace("serial=", "")
    c["not_before"] = x509(leaf, "-startdate").replace("notBefore=", "")
    c["not_after"] = x509(leaf, "-enddate").replace("notAfter=", "")
    c["fingerprint_sha256"] = x509(leaf, "-fingerprint", "-sha256").split("=", 1)[-1]
    san = x509(leaf, "-ext", "subjectAltName")
    c["sans"] = [s.strip() for s in san.split("\n", 1)[1].split(",")] if "\n" in san else []
    eku = x509(leaf, "-ext", "extendedKeyUsage")
    c["key_usage"] = [s.strip() for s in eku.split("\n", 1)[1].split(",")] if "\n" in eku else []
    c["ocsp_url"] = x509(leaf, "-ocsp_uri").split("\n")[0] if x509(leaf, "-ocsp_uri") else None
    aia = x509(leaf, "-ext", "authorityInfoAccess")
    m = re.search(r"CA Issuers\s*-\s*URI:(\S+)", aia)
    c["ca_issuer_url"] = m.group(1) if m else None
    crl = x509(leaf, "-ext", "crlDistributionPoints")
    c["crl_urls"] = re.findall(r"URI:(\S+)", crl)

    end = parse_openssl_date(c["not_after"])
    if end:
        days = (end - dt.datetime.now(dt.timezone.utc)).days
        c["days_to_expiry"] = days
        if days < 0:
            rep.fail("certificate", "certificate EXPIRED %d days ago" % -days)
        elif days < EXPIRY_WARN_DAYS:
            rep.warn("certificate", "certificate expires in %d days" % days)
        else:
            rep.ok("certificate", "certificate valid for another %d days" % days)
    if not c["ocsp_url"]:
        rep.warn("certificate", "no OCSP URL in the cert; clients will go straight to the CRL")
    elif ignore_aia:
        rep.ok("certificate", "cert's own OCSP URL %s not tested (--ignore-aia); testing the servers file instead" % c["ocsp_url"])


def get_issuer(rep, leaf, supplied, chain_issuer, timeout, workdir, issuer_files=(), ignore_aia=False):
    """Return path to issuer PEM or None. Order: -i file, TLS chain, servers-file issuers, AIA download."""
    c = rep.certificate
    pem = None
    from_files = None
    if not supplied and not chain_issuer and issuer_files:
        from_files = pick_issuer_from_files(rep, leaf, issuer_files)
        if not from_files:
            rep.warn("issuer", "none of the %d issuer file(s) in the servers file signed this leaf" % len(issuer_files))
    if supplied:
        pem = to_pem(supplied)
        if pem:
            rep.issuer["source"] = supplied
        else:
            rep.fail("issuer", "cannot parse issuer file %s" % supplied)
            return None
    elif chain_issuer:
        with open(chain_issuer) as fh:
            pem = fh.read()
        rep.issuer["source"] = "second certificate in the TLS chain"
    elif from_files:
        pem = to_pem(from_files)
        rep.issuer["source"] = from_files + " (from servers file)"
    elif ignore_aia:
        rep.fail("issuer", "--ignore-aia set and no issuer available: use -i, or add \"issuers\" to the servers file")
        return None
    elif c.get("ca_issuer_url"):
        url = c["ca_issuer_url"]
        net = network_probe(url, timeout)
        rep.issuer["network"] = net
        rep.issuer["source"] = url
        if net["dns_error"] or (net["tcp_error"] and not net["ok"]):
            rep.fail("issuer", "cannot reach %s - %s" % (net["host"], net["dns_error"] or net["tcp_error"]))
            return None
        status, data, ms, err, info = http_get(url, timeout)
        rep.issuer["download_ms"] = ms
        rep.issuer["http"] = info
        if err or status != 200:
            rep.fail("issuer", "could not download issuer from %s (%s)" % (url, err or "HTTP %s" % status))
            return None
        raw = os.path.join(workdir, "issuer.raw")
        with open(raw, "wb") as fh:
            fh.write(data)
        pem = to_pem(raw)
        if not pem:
            rep.fail("issuer", "AIA URL answered but the content is not a certificate")
            return None
        rep.ok("issuer", "downloaded issuer from AIA in %d ms" % ms)
    else:
        rep.fail("issuer", "no issuer supplied and no CA Issuer URL in the cert; use -i issuer.pem")
        return None

    issuer = write_tmp(workdir, "issuer.pem", pem)
    rep.issuer["subject"] = re.sub(r"^subject=\s*", "", x509(issuer, "-subject"))
    rep.issuer["not_after"] = x509(issuer, "-enddate").replace("notAfter=", "")
    rc1, _ = run(["openssl", "verify", "-partial_chain", "-CAfile", issuer, leaf])
    rc2, _ = run(["openssl", "verify", "-no_check_time", "-partial_chain", "-CAfile", issuer, leaf])
    rep.issuer["verifies_leaf"] = (rc1 == 0 or rc2 == 0)
    if rep.issuer["verifies_leaf"]:
        rep.ok("issuer", "issuer signature verifies the leaf")
    else:
        rep.warn("issuer", "issuer cert does NOT verify this leaf (wrong issuer? OCSP will say unauthorized)")
    return issuer


def ocsp_check(rep, leaf, issuer, url, label, timeout):
    r = {"label": label, "url": url, "ms": None, "status": None, "result": None,
         "responder": None, "this_update": None, "next_update": None, "detail": None,
         "network": None, "raw_error": None, "_f0": len(rep.findings),
         "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")}
    rep.ocsp.append(r)

    # layer 1 and 2: DNS and TCP, timed separately so we can name the broken layer
    net = network_probe(url, timeout)
    r["network"] = net
    if net["dns_error"]:
        r["status"], r["result"] = "dns_error", "fail"
        rep.fail("ocsp", "%s: %s  (%s)" % (label, net["dns_error"], url))
        return
    if net["tcp_error"] and not net["ok"]:
        r["status"], r["result"] = "tcp_error", "fail"
        rep.fail("ocsp", "%s: %s  (%s:%s)" % (label, net["tcp_error"], net["host"], net["port"]))
        return
    if net["dns_ms"] is not None and net["dns_ms"] > 1000:
        rep.warn("ocsp", "%s: DNS lookup for %s took %d ms (slow resolver?)" % (label, net["host"], net["dns_ms"]))
    if net["tcp_ms"] is not None and net["tcp_ms"] > 1000:
        rep.warn("ocsp", "%s: TCP connect to %s:%s took %d ms" % (label, net["host"], net["port"], net["tcp_ms"]))

    # layer 3: the OCSP exchange itself
    t0 = now_ms()
    rc, out = run(["openssl", "ocsp", "-issuer", issuer, "-cert", leaf, "-url", url, "-noverify",
                   "-resp_text"], timeout=timeout)
    ms = now_ms() - t0
    r["ms"] = ms

    def field(name):
        m = re.search(r"%s\s*:\s*(.+)" % name, out)
        return m.group(1).strip() if m else None

    if rc == 124:
        r["status"] = "timeout"
        r["result"] = "fail"
        rep.fail("ocsp", "%s: TIMEOUT after %ds - TCP connected in %s ms, so the responder accepted the "
                 "connection but never answered (backend stall: HSM/DB/threads)  (%s)"
                 % (label, timeout, net["tcp_ms"], url))
        return
    if rc == 127:
        r["status"], r["result"], r["raw_error"] = "no_openssl", "fail", out
        rep.fail("ocsp", "%s: %s" % (label, out))
        return

    m = re.search(r"^%s: (good|revoked|unknown)" % re.escape(leaf), out, re.M)
    r["responder"] = field("Responder Id")
    r["this_update"] = field("This Update")
    r["next_update"] = field("Next Update")
    if m:
        r["status"] = m.group(1)
        if r["status"] == "good":
            if ms > SLOW_MS:
                r["result"] = "warn"
                rep.warn("ocsp", "%s: good but SLOW %d ms  (%s)" % (label, ms, url))
            else:
                r["result"] = "ok"
                rep.ok("ocsp", "%s: good in %d ms  (%s)" % (label, ms, url))
        elif r["status"] == "revoked":
            r["result"] = "fail"
            r["detail"] = field("Revocation Time")
            reason = field("Reason")
            rep.fail("ocsp", "%s: REVOKED%s%s  (%s)" % (label,
                     " on " + r["detail"] if r["detail"] else "",
                     " (%s)" % reason if reason else "", url))
        else:
            r["result"] = "warn"
            rep.warn("ocsp", "%s: unknown - responder serves this CA but has never seen this serial  (%s)" % (label, url))
        return

    r["result"] = "fail"
    # keep openssl's own error lines verbatim for the JSON / HTML report
    r["raw_error"] = "\n".join(l for l in out.strip().split("\n") if l.strip())[:2000] or None
    if re.search(r"Responder Error:\s*unauthorized", out, re.I):
        r["status"] = "unauthorized"
        rep.fail("ocsp", "%s: unauthorized - responder has no signing key for CA '%s'  (%s)"
                 % (label, rep.issuer.get("subject", "?"), url))
    elif re.search(r"Responder Error", out, re.I):
        r["status"] = "responder_error"
        r["detail"] = field("Responder Error")
        rep.fail("ocsp", "%s: %s  (%s)" % (label, r["detail"], url))
    elif re.search(r"code=(\d+)", out):
        # HTTP-level error from the responder or a proxy in front of it
        m = re.search(r"code=(\d+)(?:, reason=([^:\n]*))?", out)
        r["status"] = "http_error"
        r["detail"] = "HTTP %s%s" % (m.group(1), " " + m.group(2).strip() if m.group(2) else "")
        via = " via proxy %s" % net["proxy"] if net["proxy"] else ""
        rep.fail("ocsp", "%s: responder returned %s%s (%d ms)  (%s)" % (label, r["detail"], via, ms, url))
    elif re.search(r"Error querying OCSP responder|connect|refused|resolve|HTTP routines", out, re.I):
        r["status"] = "unreachable"
        m = re.search(r"Connection refused|Could not resolve[^:]*|Name or service not known|"
                      r"timed out|unreachable|Connection reset|Broken pipe", out, re.I)
        r["detail"] = m.group(0) if m else (field("error") or r["raw_error"].split("\n")[-1][:160])
        rep.fail("ocsp", "%s: cannot reach responder (%d ms)  (%s) - %s" % (label, ms, url, r["detail"]))
    else:
        r["status"] = "unexpected"
        r["detail"] = out.strip().split("\n")[0][:200]
        rep.fail("ocsp", "%s: unexpected reply (%d ms)  (%s) - %s" % (label, ms, url, r["detail"]))


def crl_check(rep, leaf, url, timeout, workdir):
    r = {"url": url, "ms": None, "size_kb": None, "entries": None, "last_update": None,
         "next_update": None, "stale": None, "serial_listed": None, "result": None, "detail": None,
         "network": None, "http": None, "_f0": len(rep.findings),
         "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")}
    rep.crl.append(r)
    if not url.startswith("http"):
        r["result"] = "skip"
        r["detail"] = "not an http URL"
        return
    net = network_probe(url, timeout)
    r["network"] = net
    if net["dns_error"] or (net["tcp_error"] and not net["ok"]):
        r["result"], r["detail"] = "fail", net["dns_error"] or net["tcp_error"]
        rep.fail("crl", "cannot reach CRL host %s - %s  (%s)" % (net["host"], r["detail"], url))
        return
    status, data, ms, err, info = http_get(url, timeout)
    r["ms"] = ms
    r["http"] = info
    if err or status != 200:
        r["result"] = "fail"
        r["detail"] = err or "HTTP %s" % status
        via = " via proxy %s" % net["proxy"] if net["proxy"] else ""
        rep.fail("crl", "CRL download failed: %s%s  (%s)" % (r["detail"], via, url))
        return
    raw = os.path.join(workdir, "crl.raw")
    with open(raw, "wb") as fh:
        fh.write(data)
    r["size_kb"] = len(data) // 1024
    fmt = "DER" if run(["openssl", "crl", "-inform", "DER", "-in", raw, "-noout"])[0] == 0 else "PEM"
    rc, text = run(["openssl", "crl", "-inform", fmt, "-in", raw, "-noout", "-text", "-lastupdate", "-nextupdate"])
    if rc != 0:
        r["result"] = "fail"
        r["detail"] = "downloaded but not parseable"
        rep.fail("crl", "CRL downloaded but not parseable  (%s)" % url)
        return
    r["entries"] = len(re.findall(r"Serial Number:", text))
    m = re.search(r"lastUpdate=(.+)", text); r["last_update"] = m.group(1).strip() if m else None
    m = re.search(r"nextUpdate=(.+)", text); r["next_update"] = m.group(1).strip() if m else None
    nu = parse_openssl_date(r["next_update"]) if r["next_update"] else None
    r["stale"] = bool(nu and nu < dt.datetime.now(dt.timezone.utc))
    serial = rep.certificate.get("serial", "")
    r["serial_listed"] = bool(serial and re.search(r"Serial Number:\s*%s\b" % re.escape(serial), text, re.I))

    msg = "CRL %d KB, %d entries, in %d ms  (%s)" % (r["size_kb"], r["entries"], ms, url)
    if ms > SLOW_MS or r["size_kb"] > BIG_CRL_KB:
        r["result"] = "warn"
        rep.warn("crl", msg + " - large/slow fallback")
    else:
        r["result"] = "ok"
        rep.ok("crl", msg)
    if r["stale"]:
        r["result"] = "fail"
        rep.fail("crl", "CRL is STALE (nextUpdate %s is in the past) - clients will reject it" % r["next_update"])
    if r["serial_listed"]:
        r["result"] = "fail"
        rep.fail("crl", "this certificate's serial IS LISTED in the CRL (revoked)")


# ------------------------------------------------------------- renderers
ANSI = {"ok": "\033[32m[ OK ]\033[0m", "warn": "\033[33m[WARN]\033[0m", "fail": "\033[31m[FAIL]\033[0m"}
PLAIN = {"ok": "[ OK ]", "warn": "[WARN]", "fail": "[FAIL]"}


def net_line(n):
    """One-line summary of a network probe: 'DNS 3 ms -> 10.1.2.3, TCP 8 ms' or the error."""
    if not n:
        return "-"
    parts = []
    if n.get("dns_error"):
        parts.append("DNS %s ms: %s" % (n.get("dns_ms"), n["dns_error"]))
    else:
        parts.append("DNS %s ms -> %s" % (n.get("dns_ms"), ", ".join(n.get("addresses") or []) or "?"))
    if n.get("proxy"):
        parts.append("via proxy %s" % n["proxy"])
    elif n.get("tcp_error") and not n.get("ok"):
        parts.append("TCP %s ms: %s" % (n.get("tcp_ms"), n["tcp_error"]))
    elif n.get("tcp_ms") is not None:
        parts.append("TCP connect %s ms" % n["tcp_ms"])
    return ", ".join(parts)


def render_text(rep, color=True):
    tag = ANSI if color else PLAIN
    b = (lambda s: "\033[1m%s\033[0m" % s) if color else (lambda s: s)
    c, i = rep.certificate, rep.issuer
    L = ["pkicheck %s  run %s on %s" % (VERSION, rep.started.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"), rep.host),
         "", b("== Certificate ==")]

    def kv(k, v):
        if v not in (None, "", []):
            L.append("  %-14s %s" % (k, ", ".join(v) if isinstance(v, list) else v))
    kv("source", c.get("source")); kv("subject", c.get("subject")); kv("issuer", c.get("issuer_dn"))
    kv("serial", c.get("serial")); kv("valid", "%s  ->  %s" % (c.get("not_before"), c.get("not_after")))
    kv("SANs", c.get("sans")); kv("key usage", c.get("key_usage"))
    kv("OCSP URL", c.get("ocsp_url") or "<none>"); kv("CA issuer", c.get("ca_issuer_url") or "<none>")
    kv("CRL URL", c.get("crl_urls") or "<none>")
    for f in rep.findings:
        if f["section"] == "certificate":
            L.append("  %s %s" % (tag[f["level"]], f["msg"]))
    L += ["", b("== Issuer certificate ==")]
    kv("source", i.get("source")); kv("issuer cert", i.get("subject")); kv("expires", i.get("not_after"))
    for f in rep.findings:
        if f["section"] == "issuer":
            L.append("  %s %s" % (tag[f["level"]], f["msg"]))
    L += ["", b("== OCSP ==")]
    if rep.servers_file:
        L.append("  %-14s %s (%d responder(s))" % ("servers file", rep.servers_file["path"], len(rep.servers_file["responders"])))
    ocsp_entries = rep.entry_findings(rep.ocsp)
    seen = set()
    for o in ocsp_entries:
        for f in o["findings"]:
            L.append("  %s %s" % (tag[f["level"]], f["msg"])); seen.add(id(f))
        L.append("    %-12s %s" % ("network", net_line(o.get("network"))))
        if o.get("responder"):
            L.append("    %-12s %s" % ("responder", o["responder"]))
        if o.get("next_update"):
            L.append("    %-12s %s" % ("next update", o["next_update"]))
        if o.get("raw_error"):
            for ln in o["raw_error"].split("\n")[:4]:
                L.append("    %-12s %s" % ("openssl", ln[:150]))
    for f in rep.findings:   # ocsp findings not tied to an entry (e.g. "cannot test without issuer")
        if f["section"] == "ocsp" and id(f) not in seen:
            L.append("  %s %s" % (tag[f["level"]], f["msg"]))
    if rep.crl:
        L += ["", b("== CRL (what clients fall back to) ==")]
        for r in rep.entry_findings(rep.crl):
            for f in r["findings"]:
                L.append("  %s %s" % (tag[f["level"]], f["msg"]))
            if r.get("network"):
                L.append("    %-12s %s" % ("network", net_line(r["network"])))
            if r.get("http") and r["http"].get("http_status"):
                L.append("    %-12s HTTP %s%s%s" % ("http", r["http"]["http_status"],
                         ", server " + r["http"]["server"] if r["http"].get("server") else "",
                         ", " + r["http"]["content_type"] if r["http"].get("content_type") else ""))
            if r.get("last_update"):
                L.append("    %-12s %s  ->  %s" % ("last/next", r["last_update"], r["next_update"]))
    L += ["", b("== Summary ==")]
    L.append("  %s: %d ok, %d warnings, %d failures" % (rep.verdict, rep.count("ok"), rep.count("warn"), rep.count("fail")))
    for f in rep.findings:
        if f["level"] == "fail":
            L.append("  %s %s" % (tag["fail"], f["msg"]))
    for f in rep.findings:
        if f["level"] == "warn":
            L.append("  %s %s" % (tag["warn"], f["msg"]))
    if rep.exit_code == 0:
        L.append("  Revocation checking for this certificate is healthy.")
    L.append("  total run time %d ms" % int((dt.datetime.now(dt.timezone.utc) - rep.started).total_seconds() * 1000))
    return "\n".join(L) + "\n"


def render_json(rep):
    return json.dumps(rep.to_dict(), indent=2) + "\n"


def render_html(rep):
    e = html.escape
    d = rep.to_dict()
    c, i = d["certificate"], d["issuer"]
    color = {"ok": "#1a7f37", "warn": "#9a6700", "fail": "#cf222e"}
    badge = {"HEALTHY": "#1a7f37", "WARNINGS": "#9a6700", "FAILURES": "#cf222e"}[d["verdict"]]

    def row(k, v):
        if v in (None, "", []):
            return ""
        v = ", ".join(v) if isinstance(v, list) else str(v)
        return "<tr><th>%s</th><td>%s</td></tr>" % (e(k), e(v))

    def findings(section):
        out = ""
        for f in d["findings"]:
            if f["section"] == section:
                out += '<li class="%s"><span class="tag">%s</span> %s</li>' % (
                    f["level"], e(f["level"].upper()), e(f["msg"]))
        return "<ul class='findings'>%s</ul>" % out if out else ""

    def raw_block(o):
        return "<tr class='raw'><td colspan='7'><pre>%s</pre></td></tr>" % e(o["raw_error"]) if o.get("raw_error") else ""

    ocsp_rows = "".join(
        "<tr class='%s'><td>%s</td><td><code>%s</code></td><td>%s</td><td class='num'>%s</td><td class='net'>%s</td><td>%s</td><td>%s</td></tr>%s" % (
            o.get("result") or "", e(o["label"]), e(o["url"]), e(o.get("status") or "-"),
            o.get("ms") if o.get("ms") is not None else "-", e(net_line(o.get("network"))),
            e(o.get("responder") or "-"), e(o.get("next_update") or o.get("detail") or "-"), raw_block(o))
        for o in d["ocsp"])
    crl_rows = "".join(
        "<tr class='%s'><td><code>%s</code></td><td class='num'>%s</td><td class='num'>%s</td><td class='num'>%s</td><td class='net'>%s</td><td>%s</td><td>%s</td></tr>" % (
            r.get("result") or "", e(r["url"]), r.get("size_kb") if r.get("size_kb") is not None else "-",
            r.get("entries") if r.get("entries") is not None else "-", r.get("ms") if r.get("ms") is not None else "-",
            e(net_line(r.get("network"))), e(r.get("next_update") or "-"),
            "stale" if r.get("stale") else ("serial listed" if r.get("serial_listed") else e(r.get("detail") or "")))
        for r in d["crl"])

    return """<!doctype html><html><head><meta charset="utf-8">
<title>pkicheck - %(subject)s</title>
<style>
 body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#1f2328}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:16px;margin:28px 0 8px;border-bottom:1px solid #d0d7de;padding-bottom:4px}
 .meta{color:#57606a;font-size:13px} .badge{display:inline-block;padding:3px 10px;border-radius:12px;color:#fff;font-weight:600;background:%(badge)s}
 table{border-collapse:collapse;width:100%%;font-size:14px} th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #eaeef2;vertical-align:top}
 table.kv th{width:140px;color:#57606a;font-weight:500} td.num{text-align:right;font-variant-numeric:tabular-nums}
 code{font-size:13px;background:#f6f8fa;padding:1px 4px;border-radius:4px}
 ul.findings{list-style:none;padding:0;margin:8px 0} ul.findings li{padding:3px 0}
 .tag{display:inline-block;min-width:44px;font-size:11px;font-weight:700;padding:1px 6px;border-radius:4px;color:#fff;text-align:center;margin-right:6px}
 li.ok .tag{background:%(c_ok)s} li.warn .tag{background:%(c_warn)s} li.fail .tag{background:%(c_fail)s}
 tr.ok td:first-child{border-left:3px solid %(c_ok)s} tr.warn td:first-child{border-left:3px solid %(c_warn)s} tr.fail td:first-child{border-left:3px solid %(c_fail)s}
 .summary{font-size:15px;margin:8px 0} td.net{font-size:12px;color:#57606a}
 tr.raw td{border-left:none;padding:0 8px 8px 24px} tr.raw pre{margin:0;font-size:11px;color:#57606a;white-space:pre-wrap;background:#f6f8fa;padding:6px;border-radius:4px}
</style></head><body>
<h1>PKI revocation check <span class="badge">%(verdict)s</span></h1>
<div class="meta">%(subject)s &middot; run %(run_at_local)s (%(run_at)s) from %(run_from)s in %(duration)d ms &middot; %(nok)d ok, %(nwarn)d warnings, %(nfail)d failures</div>

<h2>Certificate</h2>
<table class="kv">%(cert_rows)s</table>%(cert_findings)s

<h2>Issuer</h2>
<table class="kv">%(issuer_rows)s</table>%(issuer_findings)s

<h2>OCSP</h2>
<table><tr><th>Test</th><th>Responder URL</th><th>Status</th><th>ms</th><th>Network (DNS / TCP)</th><th>Responder ID</th><th>Next update / detail</th></tr>%(ocsp_rows)s</table>%(ocsp_findings)s

<h2>CRL fallback</h2>
<table><tr><th>URL</th><th>KB</th><th>Entries</th><th>ms</th><th>Network (DNS / TCP)</th><th>Next update</th><th>Note</th></tr>%(crl_rows)s</table>%(crl_findings)s

<h2>Summary</h2>
<div class="summary">%(summary_line)s</div>
<p class="meta">Generated by pkicheck.py %(version)s. Thresholds: slow &gt; %(slow)d ms, large CRL &gt; %(bigcrl)d KB, expiry warning &lt; %(expdays)d days.</p>
</body></html>
""" % {
        "subject": e(c.get("subject", "")), "badge": badge, "verdict": d["verdict"],
        "run_at": e(d["run_at"]), "run_at_local": e(d["run_at_local"]), "duration": d["duration_ms"], "run_from": e(d["run_from"]),
        "nok": d["summary"]["ok"], "nwarn": d["summary"]["warn"], "nfail": d["summary"]["fail"],
        "c_ok": color["ok"], "c_warn": color["warn"], "c_fail": color["fail"],
        "cert_rows": row("Source", c.get("source")) + row("Subject", c.get("subject")) + row("Issuer DN", c.get("issuer_dn"))
                     + row("Serial", c.get("serial")) + row("Valid from", c.get("not_before")) + row("Valid to", c.get("not_after"))
                     + row("Days left", c.get("days_to_expiry")) + row("SANs", c.get("sans")) + row("Key usage", c.get("key_usage"))
                     + row("OCSP URL", c.get("ocsp_url")) + row("CA issuer URL", c.get("ca_issuer_url")) + row("CRL URLs", c.get("crl_urls"))
                     + row("SHA-256", c.get("fingerprint_sha256")),
        "cert_findings": findings("certificate"),
        "issuer_rows": row("Source", i.get("source")) + row("Subject", i.get("subject")) + row("Expires", i.get("not_after"))
                       + row("Verifies leaf", i.get("verifies_leaf")),
        "issuer_findings": findings("issuer"),
        "ocsp_rows": ocsp_rows or "<tr><td colspan='6'>not tested</td></tr>", "ocsp_findings": findings("ocsp"),
        "crl_rows": crl_rows or "<tr><td colspan='6'>not tested</td></tr>", "crl_findings": findings("crl"),
        "summary_line": "Revocation checking for this certificate is healthy." if d["exit_code"] == 0 else
                        "%d failure(s), %d warning(s) - see above." % (d["summary"]["fail"], d["summary"]["warn"]),
        "version": VERSION, "slow": SLOW_MS, "bigcrl": BIG_CRL_KB, "expdays": EXPIRY_WARN_DAYS,
    }


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="PKI / OCSP troubleshooting check",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("target", help="certificate file (PEM/DER) or host:port")
    ap.add_argument("-i", "--issuer", help="issuer certificate file (skips AIA download)")
    ap.add_argument("-o", "--ocsp", action="append", default=[], metavar="URL",
                    help="extra OCSP responder to test (repeatable)")
    ap.add_argument("-t", "--timeout", type=int, default=10, help="per-request timeout in seconds (default 10)")
    ap.add_argument("--servers", metavar="FILE",
                    help='JSON file listing PKI servers to test ({"va_servers": ["host1", "host2"]})')
    ap.add_argument("--ignore-aia", "--ignore_aia", dest="ignore_aia", action="store_true",
                    help="do not use the OCSP / CA-issuer URLs printed in the cert; test only --servers and -o")
    ap.add_argument("--no-crl", action="store_true", help="skip the CRL download")
    ap.add_argument("--json", action="store_true", help="output JSON")
    ap.add_argument("--html", action="store_true", help="output an HTML report")
    ap.add_argument("-O", "--output", metavar="FILE", help="write the report to FILE instead of stdout")
    ap.add_argument("--no-color", action="store_true", help="plain text, no ANSI colours")
    args = ap.parse_args()

    rep = Report()
    responders, issuer_files = [], []
    if args.servers:
        try:
            responders, issuer_files, lb = load_servers_file(args.servers)
            rep.servers_file = {"path": args.servers, "responders": responders, "issuers": issuer_files}
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print("cannot read servers file %s: %s" % (args.servers, e), file=sys.stderr)
            sys.exit(2)
    if args.ignore_aia and not responders and not args.ocsp:
        print("--ignore-aia needs something else to test: give --servers FILE or -o URL", file=sys.stderr)
        sys.exit(2)
    responders += [{"label": "extra responder", "url": u} for u in args.ocsp]

    with tempfile.TemporaryDirectory(prefix="pkicheck.") as work:
        leaf, chain_issuer = get_certificate(rep, args.target, args.timeout, work)
        if leaf:
            describe_certificate(rep, leaf, ignore_aia=args.ignore_aia)
            issuer = get_issuer(rep, leaf, args.issuer, chain_issuer, args.timeout, work,
                                issuer_files=issuer_files, ignore_aia=args.ignore_aia)
            if issuer:
                if rep.certificate.get("ocsp_url") and not args.ignore_aia:
                    ocsp_check(rep, leaf, issuer, rep.certificate["ocsp_url"], "cert's OCSP URL", args.timeout)
                for r in responders:
                    ocsp_check(rep, leaf, issuer, r["url"], r["label"], args.timeout)
            else:
                rep.fail("ocsp", "cannot test OCSP without an issuer certificate")
            if not args.no_crl:
                for u in rep.certificate.get("crl_urls", []):
                    crl_check(rep, leaf, u, args.timeout, work)

    if args.json:
        out = render_json(rep)
    elif args.html:
        out = render_html(rep)
    else:
        out = render_text(rep, color=not args.no_color and not args.output and sys.stdout.isatty())

    if args.output:
        with open(args.output, "w") as fh:
            fh.write(out)
        print("report written to %s  (%s: %d ok, %d warn, %d fail)" % (
            args.output, rep.verdict, rep.count("ok"), rep.count("warn"), rep.count("fail")))
    else:
        sys.stdout.write(out)
    sys.exit(rep.exit_code)


if __name__ == "__main__":
    main()
