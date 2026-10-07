"""Validate, rank, save, and render local shortlist sessions (stdlib only)."""

import argparse
import base64
import copy
import fcntl
import json
import os
import re
import tempfile
import uuid
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
STATES = {"meets", "fails", "unknown", "conflicting"}
CDNS = {"cdnjs.cloudflare.com", "esm.sh", "cdn.jsdelivr.net", "unpkg.com",
        "fonts.googleapis.com", "fonts.gstatic.com", "fonts.bunny.net"}


def text(value: Any, label: str, limit: int = 8000) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"Invalid {label}")
    return value


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("Invalid identifier")
    return value


def https(value: Any) -> str:
    value = text(value, "source URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Evidence and source URLs must use HTTPS without credentials")
    return value


def canonical_url(value: str) -> str:
    """Keep listing identity separate from transaction dates and tracking."""
    parsed = urlsplit(https(value))
    host = (parsed.hostname or '').lower()
    room = re.fullmatch(r'/rooms/([0-9]+)(?:/reviews)?/?', parsed.path)
    if room and host in {'airbnb.com', 'www.airbnb.com', 'airbnb.com.br', 'www.airbnb.com.br'}:
        return 'https://www.airbnb.com/rooms/' + room[1]
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith('utm_') and key.lower() not in {'fbclid', 'gclid'}]
    return urlunsplit(('https', parsed.netloc.lower(), parsed.path or '/', urlencode(sorted(query)), ''))


def validate(data: Any) -> dict:
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported session format")
    identifier(data.get("id"))
    if type(data.get("revision")) is not int or data["revision"] < 0:
        raise ValueError("Invalid revision")
    if data.get("confirmed") is not True:
        raise ValueError("Confirm the criterion profile before saving or rendering")
    for key in ("title", "query"):
        if not text(data.get(key), key).strip():
            raise ValueError(f"Empty {key}")
    if data.get('language', 'en') not in {'en', 'pt-BR'}:
        raise ValueError('Unsupported interface language')
    if not isinstance(data.get('known_urls', []), list):
        raise ValueError('Known URLs must be a list')
    for url in data.get('known_urls', []):
        https(url)
    criteria = data.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("A confirmed criterion profile is required")
    criterion_ids = set()
    for criterion in criteria:
        if not isinstance(criterion, dict):
            raise ValueError("Invalid criterion")
        cid = identifier(criterion.get("id"))
        if cid in criterion_ids or criterion.get("kind") not in {"must", "preference"}:
            raise ValueError("Duplicate criterion or invalid criterion kind")
        criterion_ids.add(cid)
        if not text(criterion.get("label"), "criterion label").strip():
            raise ValueError("Empty criterion label")
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Invalid candidates")
    candidate_ids = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("Invalid candidate")
        cid = identifier(candidate.get("id"))
        if cid in candidate_ids:
            raise ValueError("Duplicate candidate identifier")
        candidate_ids.add(cid)
        if not text(candidate.get("name"), "candidate name").strip():
            raise ValueError("Empty candidate name")
        for field in ("summary", "location", "next_step"):
            text(candidate.get(field, ""), field)
        if candidate.get('url') is not None:
            https(candidate['url'])
        extras = candidate.get("extras", [])
        if not isinstance(extras, list):
            raise ValueError("Invalid extras")
        for extra in extras:
            text(extra, "extra")
        checks = candidate.get("checks")
        if not isinstance(checks, dict) or set(checks) != criterion_ids:
            raise ValueError("Each candidate needs a check for every criterion")
        for check in checks.values():
            if not isinstance(check, dict) or check.get("status") not in STATES:
                raise ValueError("Invalid criterion status")
            if not text(check.get("summary"), "check summary").strip():
                raise ValueError("Explain every criterion status")
            evidence = check.get("evidence")
            if not isinstance(evidence, list):
                raise ValueError("Invalid evidence")
            minimum = 2 if check["status"] == "conflicting" else int(check["status"] != "unknown")
            if len(evidence) < minimum:
                raise ValueError("Supported, failed, and conflicting checks require evidence")
            if type(check.get('lead', False)) is not bool:
                raise ValueError('Lead must be a boolean')
            if check.get('lead') and (check['status'] != 'unknown' or not evidence):
                raise ValueError('A verification lead requires unknown status and cited evidence')
            for item in evidence:
                if not isinstance(item, dict):
                    raise ValueError("Invalid evidence item")
                https(item.get("url"))
                for field in ("publisher", "excerpt", "scope"):
                    if not text(item.get(field), field).strip():
                        raise ValueError("Evidence requires publisher, excerpt, and scope")
                date.fromisoformat(text(item.get("checked_at"), "check date", 10))
                if item.get("published_at") is not None:
                    date.fromisoformat(text(item["published_at"], "publication date", 10))
        if candidate.get("photo") is not None:
            photo = candidate["photo"]
            if not isinstance(photo, dict):
                raise ValueError("Invalid photo")
            text(photo.get("url"), "photo", 700000)
            https(photo.get("source"))
    for key in ("decisions", "notes"):
        entries = data.get(key, {})
        if not isinstance(entries, dict) or not set(entries).issubset(candidate_ids):
            raise ValueError(f"Invalid {key} identifiers")
        for value in entries.values():
            if key == "decisions" and value not in {"save", "pass"}:
                raise ValueError("Invalid decision")
            if key == "notes":
                text(value, "reason", 2000)
    text(data.get("feedback", ""), "feedback", 4000)
    if "demo" in data and type(data["demo"]) is not bool:
        raise ValueError("Invalid demo marker")
    return data


def rank(data: dict) -> list:
    validate(data)
    must = [c["id"] for c in data["criteria"] if c["kind"] == "must"]
    preferences = [c["id"] for c in data["criteria"] if c["kind"] == "preference"]

    def priority(candidate):
        required = [candidate["checks"][key]["status"] for key in must]
        optional = [candidate["checks"][key]["status"] for key in preferences]
        leads = sum(candidate['checks'][key].get('lead', False) for key in must)
        return (required.count("conflicting"), required.count("unknown"),
                -leads, -optional.count("meets"), optional.count("fails") + optional.count("conflicting"))

    seen = {canonical_url(url) for url in data.get('known_urls', [])}
    eligible = []
    for candidate in data['candidates']:
        if any(candidate['checks'][key]['status'] == 'fails' for key in must):
            continue
        url = canonical_url(candidate['url']) if candidate.get('url') else None
        if url is not None:
            if url in seen:
                continue
            seen.add(url)
        eligible.append(candidate)
    return sorted(eligible, key=priority)


def read(path: Path) -> dict:
    if path.is_symlink():
        raise ValueError("Session files cannot be symlinks")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def load(session_id: str, directory: Path) -> dict:
    session_id = identifier(session_id)
    data = read(directory / f"{session_id}.json")
    if data["id"] != session_id:
        raise ValueError("Session file identity mismatch")
    return data


def save(data: dict, directory: Path) -> dict:
    validate(data)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    ignore = directory / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    target = directory / f"{data['id']}.json"
    lock = directory / ".lock"
    if lock.is_symlink():
        raise ValueError("Session lock cannot be a symlink")
    # ponytail: one directory lock; per-session locks if concurrent search throughput matters.
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        expected = load(data["id"], directory)["revision"] if target.exists() else 0
        if target.is_symlink() or data["revision"] != expected:
            raise ValueError("Revision conflict; reload before saving pending choices")
        stored = copy.deepcopy(data)
        stored["revision"] = expected + 1
        stored["saved_at"] = datetime.now(timezone.utc).isoformat()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as out:
                temporary = Path(out.name)
                json.dump(stored, out, ensure_ascii=False, indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, target)
            result = load(stored["id"], directory)
            if result != stored:
                raise ValueError("Saved session could not be verified")
            return result
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def apply(payload: Any, directory: Path) -> dict:
    if not isinstance(payload, dict) or payload.get("version") != 1 or payload.get("action") not in {"save", "refine"}:
        raise ValueError("Invalid handoff action")
    data = load(identifier(payload.get("session_id")), directory)
    if type(payload.get("revision")) is not int or payload["revision"] != data["revision"]:
        raise ValueError("Revision conflict; reload before applying pending choices")
    for key in ("decisions", "notes", "feedback"):
        if key not in payload:
            raise ValueError("Handoff must include the complete review snapshot")
        data[key] = payload[key]
    return save(validate(data), directory)


def display_photo(url: str) -> bool:
    if url.startswith("data:image/"):
        match = re.fullmatch(r"data:image/(?:png|jpeg|webp|gif);base64,([A-Za-z0-9+/=]+)", url)
        if not match:
            return False
        try:
            base64.b64decode(match[1], validate=True)
        except ValueError:
            return False
        return True
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname in CDNS and not parsed.username and not parsed.password


def render(data: dict, output: Path, standalone: bool = False) -> None:
    validate(data)
    view = copy.deepcopy(data)
    view["eligible"] = [c["id"] for c in rank(data)]
    for candidate in view["candidates"]:
        if candidate.get("photo"):
            candidate["photo"]["displayable"] = display_photo(candidate["photo"]["url"])
    encoded = json.dumps(view, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = (Path(__file__).resolve().parents[1] / "assets/evidence-desk.html").read_text(encoding="utf-8")
    if data.get('language') == 'pt-BR':
        translations = json.loads((Path(__file__).resolve().parents[1] / 'assets/pt-BR.json').read_text(encoding='utf-8'))
        # Translate the template before inserting data, so names, reasons and sources stay intact.
        pattern = '|'.join(re.escape(key) for key in sorted(translations, key=len, reverse=True))
        template = re.sub(pattern, lambda match: translations[match[0]], template)
    fragment = template.replace("__ROOT_ID__", "shortlist-" + uuid.uuid4().hex[:12]).replace("__SESSION_JSON__", encoded)
    if len(fragment.encode("utf-8")) >= 1000000:
        raise ValueError("Inline result exceeds the host size limit; reduce the displayed batch or photo sizes")
    if standalone:
        fragment = (f'<!doctype html>\n<html lang="{data.get("language", "en")}"><head>'
                    '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                    f'<title>{escape(data["title"])}</title><style>'
                    ':root{color-scheme:light dark}body{margin:0;padding:24px;background:light-dark(#f7f5fb,#19171e)}'
                    'main{max-width:1100px;margin:auto}@media(max-width:650px){body{padding:12px}}'
                    f'</style></head><body><main>{fragment}</main></body></html>')
    output.write_text(fragment, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("save", "load", "apply"):
        p = sub.add_parser(command)
        p.add_argument("input")
        p.add_argument("--directory", type=Path, default=Path.cwd() / ".shortlist")
    p = sub.add_parser("render")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--standalone", action="store_true", help="Write a complete HTML page for a local browser")
    args = parser.parse_args()
    try:
        if args.command == "render":
            render(read(args.input), args.output, standalone=args.standalone)
            print(args.output)
            return
        if args.command == "load":
            result = load(args.input, args.directory)
        elif args.command == "save":
            result = save(read(Path(args.input)), args.directory)
        else:
            result = apply(json.loads(Path(args.input).read_text(encoding="utf-8")), args.directory)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(1, f"Session operation failed: {error}\n")


if __name__ == "__main__":
    main()
