import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("session", ROOT / "skills/shortlist/scripts/session.py")
assert spec is not None and spec.loader is not None
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


def evidence(label="Synthetic source"):
    return {"url": "https://example.invalid/source", "publisher": label,
            "excerpt": "Explicit synthetic claim", "checked_at": "2026-10-06",
            "scope": "Exact synthetic service, branch, or listing"}


def candidate(cid, required, preferred):
    def check(status):
        count = 2 if status == "conflicting" else int(status != "unknown")
        return {"status": status, "summary": "Synthetic " + status,
                "evidence": [evidence(f"Synthetic source {i}") for i in range(count)]}
    return {"id": cid, "name": "Synthetic " + cid, "checks": {
        "required": check(required), "preferred": check(preferred)}}


def example(domain="restaurant"):
    return {"version": 1, "id": "test-" + domain, "revision": 0, "demo": True,
            "title": "Synthetic " + domain, "query": "Compare synthetic " + domain,
            "confirmed": True, "criteria": [
                {"id": "required", "label": "Required service", "kind": "must"},
                {"id": "preferred", "label": "Preferred atmosphere", "kind": "preference"}],
            "candidates": [candidate("no-pref", "meets", "fails"),
                           candidate("unknown-must", "unknown", "meets"),
                           candidate("conflict-must", "conflicting", "meets"),
                           candidate("excluded", "fails", "meets"),
                           candidate("unknown-pref", "meets", "unknown"),
                           candidate("full", "meets", "meets")],
            "decisions": {}, "notes": {}, "feedback": ""}


class SessionChecks(unittest.TestCase):
    def test_standalone_cli_wraps_safe_localized_html_and_preserves_fragment_default(self):
        data = example()
        data.update(language='pt-BR', title='Dinner </title><script>window.bad=true</script> & friends')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'demo.json'
            source.write_text(json.dumps(data))
            output = Path(directory) / 'view.html'
            command = [sys.executable, str(ROOT / 'skills/shortlist/scripts/session.py'),
                       'render', str(source), str(output)]
            subprocess.run(command + ['--standalone'], check=True, capture_output=True)
            content = output.read_text()
            self.assertTrue(content.startswith('<!doctype html>'))
            self.assertIn('<html lang="pt-BR">', content)
            self.assertIn('name="viewport"', content)
            self.assertIn('&lt;/title&gt;&lt;script&gt;', content)
            self.assertNotIn('<script>window.bad=true</script>', content)
            self.assertIn('Salvar sessão', content)
            self.assertLess(content.index('<body>'), content.index('data-session'))
            subprocess.run(command, check=True, capture_output=True)
            self.assertNotIn('<!doctype html>', output.read_text())

    def test_unknown_lead_requires_evidence_and_stays_unknown(self):
        data = example()
        first = candidate('no-lead', 'unknown', 'meets')
        second = candidate('lead', 'unknown', 'unknown')
        second['checks']['required'].update(lead=True, evidence=[evidence()])
        data['candidates'] = [first, second]
        self.assertEqual([c['id'] for c in session.rank(data)], ['lead', 'no-lead'])
        self.assertEqual(second['checks']['required']['status'], 'unknown')
        second['checks']['required']['evidence'] = []
        with self.assertRaises(ValueError):
            session.validate(data)
        second['checks']['required'].update(status='meets', evidence=[evidence()])
        with self.assertRaises(ValueError):
            session.validate(data)

    def test_known_listing_and_batch_duplicates_use_url_identity(self):
        data = example()
        data['known_urls'] = ['https://www.airbnb.com.br/rooms/123?check_in=2027-03-19&adults=5']
        data['candidates'] = [candidate('known', 'meets', 'meets'),
                              candidate('new', 'meets', 'unknown'),
                              candidate('duplicate', 'meets', 'meets')]
        data['candidates'][0]['url'] = 'https://www.airbnb.com/rooms/123?guests=5#availability'
        data['candidates'][1]['url'] = 'https://www.airbnb.com.br/rooms/456?adults=5'
        data['candidates'][2]['url'] = 'https://www.airbnb.com/rooms/456?check_out=2027-03-22'
        self.assertEqual([c['id'] for c in session.rank(data)], ['new'])
        self.assertEqual(session.canonical_url('https://www.airbnb.com.br/rooms/123/reviews?adults=5'),
                         session.canonical_url('https://www.airbnb.com/rooms/123'))
        # Different branches are distinct, while tracking parameters are not.
        self.assertEqual(session.canonical_url('https://example.com/menu?branch=moema&utm_source=ig#top'),
                         session.canonical_url('https://example.com/menu?branch=moema'))
        self.assertNotEqual(session.canonical_url('https://example.com/menu?branch=moema'),
                            session.canonical_url('https://example.com/menu?branch=pinheiros'))
        self.assertNotEqual(session.canonical_url('https://notairbnb.com/rooms/123'),
                            session.canonical_url('https://www.airbnb.com/rooms/123'))
        for invalid in ['not a URL', 'https://user:pass@example.com/', 'javascript:alert(1)']:
            data['known_urls'] = [invalid]
            with self.assertRaises(ValueError):
                session.validate(data)

    def test_portuguese_render_preserves_user_text_and_single_candidate(self):
        data = example()
        data.update(language='pt-BR', known_urls=[])
        data['candidates'] = [candidate('only', 'unknown', 'meets')]
        data['candidates'][0].update(name='Save session', next_step='Confirmar o total com taxas.')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'view.html'
            session.render(data, output)
            content = output.read_text()
            self.assertIn('Salvar sessão', content)
            self.assertIn('Confirmar o total com taxas.', content)
            self.assertIn('"name": "Save session"', content)
            self.assertIn('"eligible": ["only"]', content)

    def test_rank_unknown_beats_failure_and_conflict(self):
        self.assertEqual([c["id"] for c in session.rank(example())],
                         ["full", "unknown-pref", "no-pref", "unknown-must", "conflict-must"])

    def test_save_apply_restore_and_removed_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = session.save(example(), root)
            self.assertEqual(saved["revision"], 1)
            self.assertEqual(session.load(saved["id"], root), saved)
            self.assertEqual((root / ".gitignore").read_text(), "*\n")
            self.assertEqual((root / f"{saved['id']}.json").stat().st_mode & 0o777, 0o600)
            payload = {"version": 1, "session_id": saved["id"], "revision": 1,
                       "action": "save", "decisions": {"full": "save"},
                       "notes": {"full": "explicit reason"}, "feedback": ""}
            next_saved = session.apply(payload, root)
            self.assertEqual(next_saved["revision"], 2)
            self.assertEqual(next_saved["notes"]["full"], "explicit reason")
            payload.update(revision=2, decisions={})
            self.assertEqual(session.apply(payload, root)["decisions"], {})

    def test_stale_handoff_preserves_newer_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = session.save(example(), root)
            payload = {"version": 1, "session_id": saved["id"], "revision": 0,
                       "action": "refine", "decisions": {}, "notes": {}, "feedback": "more"}
            with self.assertRaisesRegex(ValueError, "Revision conflict"):
                session.apply(payload, root)
            self.assertEqual(session.load(saved["id"], root), saved)

    def test_failed_atomic_replace_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = session.save(example(), root)
            saved["notes"] = {"full": "pending"}
            original = (root / f"{saved['id']}.json").read_bytes()
            with patch.object(session.os, "replace", side_effect=OSError("disk unavailable")), self.assertRaises(OSError):
                session.save(saved, root)
            self.assertEqual((root / f"{saved['id']}.json").read_bytes(), original)
            self.assertEqual({p.name for p in root.iterdir()}, {".gitignore", ".lock", f"{saved['id']}.json"})

    def test_invalid_data_and_symlink_are_rejected(self):
        variants = []
        for change in [lambda d: d.update(confirmed=False), lambda d: d.update(id="../../escape"),
                       lambda d: d.update(revision=True), lambda d: d.update(decisions={"missing": "save"})]:
            data = example(); change(data); variants.append(data)
        data = example(); data["candidates"][0]["checks"]["required"]["evidence"] = []; variants.append(data)
        data = example(); data["candidates"][0]["checks"]["required"]["evidence"][0]["url"] = "javascript:alert(1)"; variants.append(data)
        for data in variants:
            with self.subTest(data=data), self.assertRaises(ValueError):
                session.validate(data)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            other = root / "other.json"; other.write_text(json.dumps(example()))
            (root / "test-restaurant.json").symlink_to(other)
            before = other.read_bytes()
            with self.assertRaises(ValueError):
                session.save(example(), root)
            self.assertEqual(other.read_bytes(), before)

    def test_photo_policy_and_domain_scope(self):
        self.assertFalse(session.display_photo("https://unapproved.example/photo.jpg"))
        self.assertFalse(session.display_photo("javascript:alert(1)"))
        self.assertFalse(session.display_photo("data:image/svg+xml;base64,PHN2Zz4="))
        self.assertTrue(session.display_photo("https://cdn.jsdelivr.net/photo.jpg"))
        for domain, scope in [("therapist", "Exact online service and insurance plan"),
                              ("restaurant", "Exact branch, Friday hours, dated menu"),
                              ("apartment", "Exact rental listing, rent plus condominium costs")]:
            data = example(domain)
            data["candidates"][0]["checks"]["required"]["evidence"][0]["scope"] = scope
            self.assertEqual(session.validate(data)["candidates"][0]["checks"]["required"]["evidence"][0]["scope"], scope)

    def test_render_neutralizes_untrusted_markup(self):
        data = example()
        data["candidates"][0]["name"] = '</script><script>window.injected=true</script>'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "view.html"
            session.render(data, output)
            self.assertNotIn('<script>window.injected=true</script>', output.read_text())
            self.assertIn('\\u003c/script\\u003e', output.read_text())


if __name__ == "__main__":
    unittest.main()
