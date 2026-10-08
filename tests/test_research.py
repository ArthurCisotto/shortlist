import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('research', ROOT / 'scripts/eval_research.py')
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


class ResearchSuiteChecks(unittest.TestCase):
    def test_recovery_requires_initial_failure_then_retrieved_guides(self):
        cases, pages, key = research.load()
        expected = key['docs-recovery']
        self.assertEqual(expected['status'], 'meets')
        first = expected['initial_failure']
        self.assertEqual(pages[first['path']]['status'], first['status'])
        origin = 'http://localhost:123'
        response = {'docs-recovery': {'status': 'meets', 'reason': 'Offline operation and creation/edit guides support all clauses.',
                                     'sources': [origin + p for p in expected['required']], 'unknown_reason': None}}
        guides = [{'path': p, 'status': 200} for p in expected['required']]
        self.assertFalse(research.grade(response, {'docs-recovery': expected}, [first] + guides, origin))
        self.assertTrue(research.grade(response, {'docs-recovery': expected}, guides, origin))
        self.assertTrue(research.grade(response, {'docs-recovery': expected}, guides + [first], origin))
        self.assertTrue(research.grade(response, {'docs-recovery': expected}, [first] + guides[:-1], origin))

    def test_grade_requires_verdict_and_observed_decisive_sources(self):
        key = {'x': {'status': 'conflicting', 'required': ['/start', '/rules'],
                     'allowed': ['/start', '/rules'], 'unknown_reason': None}}
        response = {'x': {'status': 'conflicting', 'reason': 'Policies disagree.',
                          'sources': ['http://localhost:123/start', 'http://localhost:123/rules'],
                          'unknown_reason': None}}
        logs = [{'path': '/start', 'status': 200}, {'path': '/rules', 'status': 200}]
        self.assertEqual(research.grade(response, key, logs, 'http://localhost:123'), [])
        self.assertTrue(research.grade(response, key, logs[:1], 'http://localhost:123'))
        response['x']['sources'] = ['http://elsewhere.test/start', 'http://localhost:123/rules']
        self.assertTrue(research.grade(response, key, logs, 'http://localhost:123'))
        response['x']['sources'] = ['http://[invalid']
        self.assertTrue(research.grade(response, key, logs, 'http://localhost:123'))
        response['x']['sources'] = ['http://localhost:123/start']
        self.assertTrue(research.grade(response, key, logs, 'http://localhost:123'))
        self.assertTrue(research.grade([], key, logs, 'http://localhost:123'))

    def test_server_only_serves_public_fixture_pages_and_records_access_failures(self):
        pages = {'/start': {'body': '<a href="/blocked">Terms</a>'},
                 '/blocked': {'status': 403, 'body': 'Access unavailable'}}
        with research.site(pages) as (origin, logs):
            self.assertIn(b'Terms', urlopen(origin + '/start').read())
            for path, status in [('/blocked', 403), ('/answer_key.json', 404), ('/../answer_key.json', 404)]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(origin + path)
                self.assertEqual(error.exception.code, status)
                error.exception.close()
        self.assertEqual([item['status'] for item in logs], [200, 403, 404, 404])

    def test_run_distinguishes_agent_infrastructure_error(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            executable = directory / 'claude'
            executable.write_text(f'#!{sys.executable}\nimport sys\nsys.stdin.read()\nsys.exit(7)\n')
            executable.chmod(0o755)
            output = directory / 'output'
            run = subprocess.run([sys.executable, str(ROOT / 'scripts/eval_research.py'),
                                  'run', '--output', str(output), '--model', 'fixed-test-model'], capture_output=True, text=True,
                                 env={**os.environ, 'PATH': str(directory) + os.pathsep + os.environ['PATH']})
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertTrue((output / 'retrievals.json').exists())
            self.assertFalse((output / 'report.json').exists())
            self.assertTrue((output / 'pages.json').exists())
            self.assertTrue((output / 'answer_key.json').exists())
            command = json.loads((output / 'command.json').read_text())
            self.assertEqual(command[-2:], ['--model', 'fixed-test-model'])

    def test_regrade_uses_frozen_key_and_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            frozen = {'archived': {'status': 'meets', 'required': ['/old'],
                                  'allowed': ['/old'], 'unknown_reason': None}}
            data = {'cases': [{'id': 'archived'}], 'answer_key': frozen,
                    'retrievals': {'origin': 'http://localhost:123',
                                  'requests': [{'path': '/old', 'status': 200}]},
                    'response': {'archived': {'status': 'meets', 'reason': 'Archived fact.',
                                             'sources': ['http://localhost:123/old'],
                                             'unknown_reason': None}}}
            for name, value in data.items():
                (directory / (name + '.json')).write_text(json.dumps(value))
            run = subprocess.run([sys.executable, str(ROOT / 'scripts/eval_research.py'),
                                  'grade', str(directory)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout), {'cases': 1, 'failures': []})

    def test_public_cases_have_no_answers_and_key_sources_exist(self):
        cases, pages, key = research.load()
        self.assertEqual({c['id'] for c in cases}, set(key))
        self.assertGreaterEqual(len({c['domain'] for c in cases}), 3)
        text = research.prompt(cases, 'http://localhost:123')
        self.assertNotIn('answer_key', text)
        self.assertNotIn('expected_status', text)
        for item in key.values():
            self.assertTrue(set(item['required']) <= set(item['allowed']) <= set(pages))
        self.assertEqual({item['status'] for item in key.values()}, set(research.STATUSES))
        guessed = {cid: {'status': item['status'], 'reason': 'Guessed.',
                          'sources': ['http://localhost:123' + p for p in item['required']],
                          'unknown_reason': item['unknown_reason']} for cid, item in key.items()}
        self.assertEqual(len(research.grade(guessed, key, [], 'http://localhost:123')), len(key))
        observed = [{'path': p, 'status': page.get('status', 200)} for p, page in pages.items()]
        self.assertEqual(research.grade(guessed, key, observed, 'http://localhost:123'), [])
        for verdict in guessed.values():
            verdict['status'] = 'unknown'
            verdict['unknown_reason'] = 'not_published'
        self.assertGreaterEqual(len(research.grade(guessed, key, observed, 'http://localhost:123')), 4)


if __name__ == '__main__':
    unittest.main()
