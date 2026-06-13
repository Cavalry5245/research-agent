#!/usr/bin/env python3
"""
FastAPI Server Starter and Tester
A cross-platform script to start and test ResearchAgent FastAPI server.

Usage:
    python start_and_test_server.py              # Start server only
    python start_and_test_server.py --test       # Start server and run tests
    python start_and_test_server.py --test-only  # Test existing server

Author: ResearchAgent Project
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import urllib.request
    import urllib.error
except ImportError:
    print("Error: urllib is required but not available")
    sys.exit(1)


class Colors:
    """ANSI color codes."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        """Disable colors for Windows CMD."""
        cls.GREEN = cls.RED = cls.YELLOW = cls.BLUE = cls.BOLD = cls.RESET = ''


def supports_color() -> bool:
    """Check if terminal supports colors."""
    import platform
    if platform.system() == 'Windows':
        return bool(os.environ.get('WT_SESSION') or os.environ.get('ANSICON'))
    return True


class ServerManager:
    """Manage FastAPI server lifecycle."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765, use_color: bool = True):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.process: Optional[subprocess.Popen] = None

        if not use_color or not supports_color():
            Colors.disable()

    def _find_python(self) -> str:
        """Find the correct Python executable."""
        # Prefer current Python
        return sys.executable

    def start_server(self, background: bool = False) -> bool:
        """Start the FastAPI server."""
        print(f"{Colors.BLUE}Starting FastAPI server...{Colors.RESET}")
        print(f"  Host: {self.host}")
        print(f"  Port: {self.port}")
        print(f"  URL:  {self.base_url}")
        print()

        python_exe = self._find_python()
        cmd = [
            python_exe, "-m", "uvicorn",
            "app.main:app",
            "--host", self.host,
            "--port", str(self.port)
        ]

        if background:
            # Start in background (detached)
            try:
                if sys.platform == 'win32':
                    # Windows: use CREATE_NEW_PROCESS_GROUP
                    self.process = subprocess.Popen(
                        cmd,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                else:
                    # Unix: use nohup-like behavior
                    self.process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                print(f"{Colors.GREEN}✓ Server started in background (PID: {self.process.pid}){Colors.RESET}")
                print(f"  To stop: kill {self.process.pid}")
                print()

                # Wait for server to be ready
                return self.wait_for_server(timeout=10)

            except Exception as e:
                print(f"{Colors.RED}✗ Failed to start server: {e}{Colors.RESET}")
                return False
        else:
            # Start in foreground
            print(f"{Colors.YELLOW}Server will run in foreground. Press Ctrl+C to stop.{Colors.RESET}")
            print()
            try:
                subprocess.run(cmd)
                return True
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Server stopped by user.{Colors.RESET}")
                return True
            except Exception as e:
                print(f"{Colors.RED}✗ Failed to start server: {e}{Colors.RESET}")
                return False

    def wait_for_server(self, timeout: int = 10) -> bool:
        """Wait for server to become ready."""
        print(f"Waiting for server to be ready (timeout: {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                req = urllib.request.Request(f"{self.base_url}/health")
                with urllib.request.urlopen(req, timeout=1) as response:
                    if response.status == 200:
                        elapsed = time.time() - start_time
                        print(f"{Colors.GREEN}✓ Server is ready (took {elapsed:.1f}s){Colors.RESET}\n")
                        return True
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.5)

        print(f"{Colors.RED}✗ Server did not become ready within {timeout}s{Colors.RESET}\n")
        return False

    def stop_server(self):
        """Stop the background server."""
        if self.process:
            print(f"{Colors.YELLOW}Stopping server (PID: {self.process.pid})...{Colors.RESET}")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                print(f"{Colors.GREEN}✓ Server stopped{Colors.RESET}")
            except subprocess.TimeoutExpired:
                self.process.kill()
                print(f"{Colors.YELLOW}⚠ Server killed (did not stop gracefully){Colors.RESET}")


class APITester:
    """Test FastAPI endpoints."""

    def __init__(self, base_url: str, use_color: bool = True):
        self.base_url = base_url
        self.results: List[Dict] = []

        if not use_color or not supports_color():
            Colors.disable()

    def _make_request(self, endpoint: str, method: str = "GET", timeout: int = 10) -> Tuple[bool, int, str, str]:
        """
        Make HTTP request.
        Returns: (success, status_code, response_body, error_message)
        """
        url = f"{self.base_url}{endpoint}"

        try:
            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode('utf-8')
                return True, response.status, body, ""

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ""
            return False, e.code, body, str(e)

        except urllib.error.URLError as e:
            return False, 0, "", f"Connection error: {e.reason}"

        except Exception as e:
            return False, 0, "", str(e)

    def test_endpoint(self, name: str, endpoint: str, expected_status: int = 200) -> Dict:
        """Test a single endpoint."""
        result = {
            'name': name,
            'endpoint': endpoint,
            'passed': False,
            'status_code': 0,
            'response': None,
            'error': ''
        }

        success, status_code, body, error = self._make_request(endpoint)
        result['status_code'] = status_code
        result['passed'] = status_code == expected_status

        if success:
            try:
                result['response'] = json.loads(body)
            except json.JSONDecodeError:
                result['response'] = body
        else:
            result['error'] = error

        # Print result
        icon = f"{Colors.GREEN}✓{Colors.RESET}" if result['passed'] else f"{Colors.RED}✗{Colors.RESET}"
        status_color = Colors.GREEN if result['passed'] else Colors.RED
        print(f"{icon} {name}")
        print(f"    {endpoint}")
        print(f"    Status: {status_color}{status_code}{Colors.RESET}")

        if result['passed'] and result['response']:
            # Show key info from response
            if isinstance(result['response'], dict):
                if 'status' in result['response']:
                    print(f"    Response: {result['response']['status']}")
                elif 'tools' in result['response']:
                    tools_count = len(result['response']['tools'])
                    print(f"    Response: {tools_count} tools found")
        elif result['error']:
            print(f"    {Colors.RED}Error: {result['error']}{Colors.RESET}")

        print()

        self.results.append(result)
        return result

    def run_all_tests(self):
        """Run all API tests."""
        print(f"{Colors.BOLD}{Colors.BLUE}Testing API Endpoints{Colors.RESET}")
        print("=" * 50)
        print()

        # Test 1: Health check
        self.test_endpoint(
            "Health Check",
            "/health"
        )

        # Test 2: MCP Tools Health
        self.test_endpoint(
            "MCP Tools Health",
            "/research-runs/tools/health"
        )

        # Test 3: API Docs (OpenAPI)
        self.test_endpoint(
            "API Documentation",
            "/docs",
            expected_status=200
        )

        # Summary
        passed = sum(1 for r in self.results if r['passed'])
        total = len(self.results)

        print(f"{Colors.BOLD}Test Summary{Colors.RESET}")
        print("=" * 50)

        if passed == total:
            print(f"{Colors.GREEN}✓ All tests passed ({passed}/{total}){Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}⚠ {passed}/{total} tests passed{Colors.RESET}")

        return passed == total

    def get_json_report(self) -> str:
        """Return test results as JSON."""
        return json.dumps({
            'base_url': self.base_url,
            'results': self.results,
            'summary': {
                'total': len(self.results),
                'passed': sum(1 for r in self.results if r['passed']),
                'failed': sum(1 for r in self.results if not r['passed'])
            }
        }, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='Start and test ResearchAgent FastAPI server'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Server host (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8765,
        help='Server port (default: 8765)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run tests after starting server'
    )
    parser.add_argument(
        '--test-only',
        action='store_true',
        help='Test existing server without starting'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output test results as JSON'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    args = parser.parse_args()

    use_color = not args.no_color

    # Test only mode
    if args.test_only:
        print(f"{Colors.BOLD}Testing existing server at http://{args.host}:{args.port}{Colors.RESET}\n")
        tester = APITester(f"http://{args.host}:{args.port}", use_color)
        success = tester.run_all_tests()

        if args.json:
            print("\n" + tester.get_json_report())

        sys.exit(0 if success else 1)

    # Start server
    manager = ServerManager(args.host, args.port, use_color)

    if args.test:
        # Start in background and test
        if not manager.start_server(background=True):
            sys.exit(1)

        try:
            tester = APITester(manager.base_url, use_color)
            success = tester.run_all_tests()

            if args.json:
                print("\n" + tester.get_json_report())

            print(f"\n{Colors.YELLOW}Note: Server is still running in background.{Colors.RESET}")
            print(f"To stop: kill {manager.process.pid}")

            sys.exit(0 if success else 1)

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Tests interrupted by user.{Colors.RESET}")
            manager.stop_server()
            sys.exit(1)
    else:
        # Start in foreground
        manager.start_server(background=False)


if __name__ == '__main__':
    main()
