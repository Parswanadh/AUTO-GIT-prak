import argparse
import json
import pathlib
import subprocess
import time


def discover_files(scope: str):
    root = pathlib.Path(scope)
    if root.is_file():
        return [str(root).replace('\\', '/')]
    return sorted(str(p).replace('\\', '/') for p in root.rglob('test_*.py'))


def run_scope(conda_py: str, scope: str, timeout_s: int):
    files = discover_files(scope)
    report = {
        'scope': scope,
        'total_files': len(files),
        'results': [],
        'failed': [],
        'timed_out': [],
        'no_tests_collected': [],
    }
    print(f'SCOPE: {scope} | FILES: {len(files)}')

    for i, f in enumerate(files, 1):
        cmd = [
            conda_py,
            '-m',
            'pytest',
            f,
            '-q',
            '-m',
            'unit or integration or e2e or diagnostic or benchmark',
        ]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
            dur = round(time.time() - t0, 2)
            rec = {'file': f, 'exit': proc.returncode, 'duration_s': dur}
            if proc.returncode == 5:
                rec['status'] = 'no_tests_collected'
                rec['stdout_tail'] = (proc.stdout or '')[-12000:]
                rec['stderr_tail'] = (proc.stderr or '')[-6000:]
                report['no_tests_collected'].append(f)
            elif proc.returncode != 0:
                rec['status'] = 'failed'
                rec['stdout_tail'] = (proc.stdout or '')[-12000:]
                rec['stderr_tail'] = (proc.stderr or '')[-6000:]
                report['failed'].append(f)
            else:
                rec['status'] = 'passed'
            report['results'].append(rec)
            print(f'[{i}/{len(files)}] exit={proc.returncode} {dur}s {f}')
        except subprocess.TimeoutExpired as e:
            dur = round(time.time() - t0, 2)
            rec = {
                'file': f,
                'exit': 'TIMEOUT',
                'status': 'timeout',
                'duration_s': dur,
                'stdout_tail': (e.stdout or '')[-12000:],
                'stderr_tail': (e.stderr or '')[-6000:],
            }
            report['results'].append(rec)
            report['failed'].append(f)
            report['timed_out'].append(f)
            print(f'[{i}/{len(files)}] TIMEOUT {dur}s {f}')

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--conda-python', default=r'D:\.conda\envs\auto-git\python.exe')
    ap.add_argument('--timeout', type=int, default=90)
    ap.add_argument('--scopes', nargs='+', default=['tests/unit', 'tests/integration', 'tests/e2e'])
    ap.add_argument('--out', default='logs/pytest_broad_conda_report.json')
    args = ap.parse_args()

    all_reports = []
    for scope in args.scopes:
        all_reports.append(run_scope(args.conda_python, scope, args.timeout))

    merged = {
        'conda_python': args.conda_python,
        'timeout_s_per_file': args.timeout,
        'reports': all_reports,
        'total_failed_files': sum(len(r['failed']) for r in all_reports),
        'total_timed_out_files': sum(len(r['timed_out']) for r in all_reports),
        'total_no_tests_collected_files': sum(len(r['no_tests_collected']) for r in all_reports),
    }

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, indent=2), encoding='utf-8')
    print(f'REPORT_WRITTEN: {out_path}')
    print(f'TOTAL_FAILED_FILES: {merged["total_failed_files"]}')
    print(f'TOTAL_TIMEOUT_FILES: {merged["total_timed_out_files"]}')
    print(f'TOTAL_NO_TESTS_COLLECTED_FILES: {merged["total_no_tests_collected_files"]}')


if __name__ == '__main__':
    main()
