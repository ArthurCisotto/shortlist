import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('behavior', ROOT / 'scripts/eval_behavior.py')
behavior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(behavior)


class BehaviorSuiteChecks(unittest.TestCase):
    def test_public_grade_exit_codes_and_invalid_verdicts(self):
        valid = {cid: {'status': status, 'reason': 'Synthetic explanation.'}
                 for cid, status in behavior.answers().items()}
        cid = next(iter(valid))
        cases = [(valid, 0), ({}, 1), ([], 1),
                 ({**valid, 'extra': valid[cid]}, 1)]
        for value in ['meets', 'invalid', [], None]:
            cases.append(({**valid, cid: {'status': value, 'reason': 'Wrong.'}}, 1))
        for reason in ['', '   ', 42, None]:
            cases.append(({**valid, cid: {'status': valid[cid]['status'], 'reason': reason}}, 1))
        cases.append(({**valid, cid: {**valid[cid], 'extra': True}}, 1))
        with tempfile.TemporaryDirectory() as directory:
            response = Path(directory) / 'response.json'
            for data, code in cases:
                with self.subTest(data=data):
                    response.write_text(json.dumps(data))
                    result = subprocess.run([sys.executable, str(ROOT / 'scripts/eval_behavior.py'),
                                             'grade', str(response)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertEqual(bool(json.loads(result.stdout)['failures']), code == 1)
            response.write_text('{broken')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/eval_behavior.py'),
                                     'grade', str(response)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)

    def test_public_run_grades_response_and_reports_agent_failure(self):
        valid = {cid: {'status': status, 'reason': 'Synthetic explanation.'}
                 for cid, status in behavior.answers().items()}
        for envelope, exitcode, expected in [({'structured_output': valid}, 0, 0),
                                             ({'structured_output': {}}, 0, 1),
                                             ({'structured_output': []}, 0, 1),
                                             ({'is_error': True}, 0, 2), ({}, 7, 2)]:
            with self.subTest(envelope=envelope, exitcode=exitcode), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                executable = directory / 'claude'
                executable.write_text(f'#!{sys.executable}\nimport sys\nsys.stdin.read()\n'
                                      f'print({json.dumps(envelope)!r})\nsys.exit({exitcode})\n')
                executable.chmod(0o755)
                output = directory / 'output'
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/eval_behavior.py'),
                                         'run', '--output', str(output)], capture_output=True, text=True,
                                        env={**os.environ, 'PATH': str(directory) + os.pathsep + os.environ['PATH']})
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertTrue((output / 'agent.json').exists())
                if expected != 2:
                    report = json.loads((output / 'report.json').read_text())
                    self.assertEqual(bool(report['failures']), expected == 1)
                    self.assertEqual(report['passed'], len(valid) if expected == 0 else 0)
                else:
                    self.assertFalse((output / 'report.json').exists())

    def test_grades_wrong_missing_extra_and_malformed_verdicts(self):
        expected = {'a': 'unknown', 'b': 'fails'}
        result = {'a': {'status': 'meets', 'reason': 'Assumed it.'},
                  'extra': {'status': 'unknown', 'reason': 'Unrequested.'}}
        failures = behavior.grade(result, expected)
        self.assertEqual({f['id'] for f in failures}, {'a', 'b', 'extra'})
        self.assertTrue(behavior.grade({'a': {'status': 'unknown', 'reason': ''}}, {'a': 'unknown'}))
        self.assertTrue(behavior.grade([], expected))
        self.assertEqual(behavior.grade({'a': {'status': 'unknown', 'reason': 'Detail absent.'}},
                                        {'a': 'unknown'}), [])

    def test_prompt_has_current_policy_and_inputs_but_no_answer_key(self):
        cases = json.loads((ROOT / 'tests/behavior/cases.json').read_text())
        prompt = behavior.prompt(cases)
        public = subprocess.run([sys.executable, str(ROOT / 'scripts/eval_behavior.py'), 'prompt'],
                                capture_output=True, text=True)
        self.assertEqual(public.returncode, 0, public.stderr)
        self.assertEqual(public.stdout, prompt + '\n')
        self.assertIn('For every criterion, reason from the source', prompt)
        self.assertIn(cases[0]['criterion'], prompt)
        self.assertNotIn('expected_status', prompt)
        self.assertNotIn('answer_key', prompt)
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        self.assertEqual({c['id'] for c in cases}, set(behavior.answers()))
        self.assertTrue(all('expected' not in c for c in cases))


if __name__ == '__main__':
    unittest.main()
