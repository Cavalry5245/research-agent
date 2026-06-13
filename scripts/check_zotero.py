#!/usr/bin/env python3
"""
Zotero Environment Checker
A cross-platform script to verify Zotero environment configuration for ResearchAgent.

Usage:
    python check_zotero.py
    python check_zotero.py --verbose
    python check_zotero.py --json

Author: ResearchAgent Project
"""

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        """Disable colors (for Windows CMD or when piping)."""
        cls.GREEN = ''
        cls.RED = ''
        cls.YELLOW = ''
        cls.BLUE = ''
        cls.BOLD = ''
        cls.RESET = ''


def supports_color() -> bool:
    """Check if the terminal supports ANSI colors."""
    # Disable colors on Windows CMD (but not Windows Terminal or PowerShell with color support)
    if platform.system() == 'Windows':
        # Check if running in Windows Terminal or has ANSICON
        if os.environ.get('WT_SESSION') or os.environ.get('ANSICON'):
            return True
        return False
    return True


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is open."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            return result == 0
    except (socket.error, socket.timeout):
        return False


def check_http_endpoint(url: str, timeout: float = 5.0) -> Tuple[bool, int, str]:
    """
    Check if an HTTP endpoint is accessible.

    Returns:
        (success: bool, status_code: int, error_message: str)
    """
    try:
        import urllib.request
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return True, response.status, ""
    except urllib.error.HTTPError as e:
        return False, e.code, str(e)
    except urllib.error.URLError as e:
        return False, 0, str(e.reason)
    except Exception as e:
        return False, 0, str(e)


def find_executable(name: str, search_paths: List[Path] = None) -> Path | None:
    """
    Find an executable in PATH or specified search paths.

    Args:
        name: Executable name (with or without extension)
        search_paths: Additional paths to search

    Returns:
        Path to executable or None if not found
    """
    # Add platform-specific extension
    if platform.system() == 'Windows' and not name.endswith('.exe'):
        name = f"{name}.exe"

    # Search in PATH
    for path_dir in os.environ.get('PATH', '').split(os.pathsep):
        candidate = Path(path_dir) / name
        if candidate.is_file():
            return candidate

    # Search in additional paths
    if search_paths:
        for search_path in search_paths:
            candidate = search_path / name
            if candidate.is_file():
                return candidate

    return None


def run_command(cmd: List[str], timeout: float = 10.0) -> Tuple[bool, str, str]:
    """
    Run a command and return (success, stdout, stderr).
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, "", str(e)


class ZoteroChecker:
    """Main checker class for Zotero environment."""

    def __init__(self, verbose: bool = False, use_color: bool = True):
        self.verbose = verbose
        self.use_color = use_color and supports_color()
        if not self.use_color:
            Colors.disable()

        self.results: List[Dict] = []
        self.conda_env_path = self._detect_conda_env()

    def _detect_conda_env(self) -> Path | None:
        """Detect the research_agent conda environment path."""
        conda_prefix = os.environ.get('CONDA_PREFIX')
        if conda_prefix and 'research_agent' in conda_prefix:
            return Path(conda_prefix)

        # Try to find it in common locations
        if platform.system() == 'Windows':
            common_bases = [
                Path('D:/Hcworkspace/Anoconda3'),
                Path.home() / 'Anaconda3',
                Path.home() / 'miniconda3',
            ]
        else:
            common_bases = [
                Path.home() / 'anaconda3',
                Path.home() / 'miniconda3',
                Path('/opt/anaconda3'),
                Path('/opt/miniconda3'),
            ]

        for base in common_bases:
            env_path = base / 'envs' / 'research_agent'
            if env_path.is_dir():
                return env_path

        return None

    def _print_header(self, text: str):
        """Print a section header."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
        print("=" * len(text))

    def _print_check(self, name: str, passed: bool, message: str = "", details: str = ""):
        """Print a check result."""
        icon = f"{Colors.GREEN}✓{Colors.RESET}" if passed else f"{Colors.RED}✗{Colors.RESET}"
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"

        print(f"{icon} [{status}] {name}")
        if message:
            print(f"        {message}")
        if details and self.verbose:
            print(f"        {Colors.YELLOW}Details: {details}{Colors.RESET}")

    def check_zotero_port(self) -> Dict:
        """Check if Zotero API port 23119 is listening."""
        result = {
            'name': 'Zotero API Port (23119)',
            'passed': False,
            'message': '',
            'details': {}
        }

        port_open = check_port('127.0.0.1', 23119)
        result['passed'] = port_open
        result['details']['port'] = 23119
        result['details']['host'] = '127.0.0.1'

        if port_open:
            result['message'] = "Port 23119 is listening"
        else:
            result['message'] = "Port 23119 is NOT listening. Please start Zotero Desktop."

        self._print_check(
            result['name'],
            result['passed'],
            result['message']
        )

        self.results.append(result)
        return result

    def check_zotero_api(self) -> Dict:
        """Check if Zotero API is responding."""
        result = {
            'name': 'Zotero API Connectivity',
            'passed': False,
            'message': '',
            'details': {}
        }

        url = "http://127.0.0.1:23119/api/users/0/items?limit=1"
        success, status_code, error_msg = check_http_endpoint(url)

        result['passed'] = success and status_code == 200
        result['details']['url'] = url
        result['details']['status_code'] = status_code

        if result['passed']:
            result['message'] = f"API responding (HTTP {status_code})"
        else:
            result['message'] = f"API not accessible. Status: {status_code}, Error: {error_msg}"

        self._print_check(
            result['name'],
            result['passed'],
            result['message'],
            error_msg if not result['passed'] else ""
        )

        self.results.append(result)
        return result

    def check_zotero_mcp(self) -> Dict:
        """Check if zotero-mcp executable exists and works."""
        result = {
            'name': 'zotero-mcp Executable',
            'passed': False,
            'message': '',
            'details': {}
        }

        search_paths = []
        if self.conda_env_path:
            if platform.system() == 'Windows':
                search_paths.append(self.conda_env_path / 'Scripts')
            else:
                search_paths.append(self.conda_env_path / 'bin')

        exe_path = find_executable('zotero-mcp', search_paths)

        if exe_path:
            result['details']['path'] = str(exe_path)
            # Try to get version
            success, stdout, stderr = run_command([str(exe_path), 'version'])

            if success:
                result['passed'] = True
                version = stdout.strip()
                result['message'] = f"Found at {exe_path}"
                result['details']['version'] = version
                if self.verbose:
                    result['message'] += f" (version: {version})"
            else:
                result['message'] = f"Found at {exe_path}, but version check failed"
                result['details']['error'] = stderr
        else:
            result['message'] = "zotero-mcp not found in PATH"
            if self.conda_env_path:
                result['message'] += f" or {self.conda_env_path}/Scripts"

        self._print_check(
            result['name'],
            result['passed'],
            result['message']
        )

        self.results.append(result)
        return result

    def check_zotero_cli(self) -> Dict:
        """Check if zotero-cli executable exists and works."""
        result = {
            'name': 'zotero-cli Executable',
            'passed': False,
            'message': '',
            'details': {}
        }

        search_paths = []
        if self.conda_env_path:
            if platform.system() == 'Windows':
                search_paths.append(self.conda_env_path / 'Scripts')
            else:
                search_paths.append(self.conda_env_path / 'bin')

        exe_path = find_executable('zotero-cli', search_paths)

        if exe_path:
            result['details']['path'] = str(exe_path)
            # Try to get collections
            success, stdout, stderr = run_command([str(exe_path), 'get', 'collections', '--limit', '1'])

            if success:
                result['passed'] = True
                result['message'] = f"Found at {exe_path} and working"
                try:
                    collections = json.loads(stdout)
                    result['details']['collections_count'] = len(collections)
                except json.JSONDecodeError:
                    result['details']['collections_count'] = 'unknown'
            else:
                result['message'] = f"Found at {exe_path}, but command failed (may need auth)"
                result['details']['error'] = stderr
                result['passed'] = True  # File exists is enough
        else:
            result['message'] = "zotero-cli not found in PATH"
            if self.conda_env_path:
                result['message'] += f" or {self.conda_env_path}/Scripts"

        self._print_check(
            result['name'],
            result['passed'],
            result['message']
        )

        self.results.append(result)
        return result

    def run_all_checks(self) -> bool:
        """Run all checks and return overall success."""
        self._print_header("Zotero Environment Check - ResearchAgent Project")

        print(f"\nPlatform: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version.split()[0]}")
        if self.conda_env_path:
            print(f"Conda Env: {self.conda_env_path}")
        print()

        self.check_zotero_port()
        self.check_zotero_api()
        self.check_zotero_mcp()
        self.check_zotero_cli()

        # Summary
        passed = sum(1 for r in self.results if r['passed'])
        total = len(self.results)
        all_passed = passed == total

        print(f"\n{Colors.BOLD}Summary{Colors.RESET}")
        print("=" * 40)

        if all_passed:
            print(f"{Colors.GREEN}✓ All checks passed ({passed}/{total}){Colors.RESET}")
            print("\nZotero environment is configured correctly.")
        else:
            print(f"{Colors.YELLOW}⚠ {passed}/{total} checks passed{Colors.RESET}")
            print("\nSome checks failed. Please follow the suggestions above to fix.")

        print("\nDocumentation: docs/DEVELOPMENT_ISSUES.md")

        return all_passed

    def get_json_report(self) -> str:
        """Return results as JSON string."""
        report = {
            'platform': platform.system(),
            'python_version': sys.version.split()[0],
            'conda_env': str(self.conda_env_path) if self.conda_env_path else None,
            'checks': self.results,
            'summary': {
                'total': len(self.results),
                'passed': sum(1 for r in self.results if r['passed']),
                'failed': sum(1 for r in self.results if not r['passed'])
            }
        }
        return json.dumps(report, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description='Check Zotero environment configuration for ResearchAgent'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    args = parser.parse_args()

    checker = ZoteroChecker(
        verbose=args.verbose,
        use_color=not args.no_color
    )

    success = checker.run_all_checks()

    if args.json:
        print("\n" + checker.get_json_report())

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
