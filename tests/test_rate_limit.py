#!/usr/bin/env python3
"""Rate Limiting Test Script

This script tests the rate limiting functionality of the PAT API.
It makes multiple requests to verify that rate limiting is enforced correctly.

Usage:
    python test_rate_limit.py [OPTIONS]

Options:
    --url URL           API base URL (default: http://localhost:8000)
    --limit LIMIT       Expected rate limit per minute (default: 60)
    --endpoint PATH     API endpoint to test (default: /api/v1/auth/login)
    --requests COUNT    Number of requests to make (default: limit + 10)
    --verbose           Show detailed output for each request
    --wait SECONDS      Wait time between requests in seconds (default: 0)
    --shared            Test shared rate limiting across multiple endpoints

Examples:
    # Test with default settings (60 req/min)
    python test_rate_limit.py

    # Test with custom rate limit
    python test_rate_limit.py --limit 100

    # Test specific endpoint with verbose output
    python test_rate_limit.py --endpoint /health --verbose

    # Test shared rate limiting across multiple endpoints
    python test_rate_limit.py --shared --verbose

    # Test with wait time between requests
    python test_rate_limit.py --wait 0.5
"""
import argparse
import requests
import time
from datetime import datetime
from typing import Dict, List, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


class RateLimitTester:
    """Test rate limiting functionality."""

    # Endpoints for shared rate limiting test
    SHARED_ENDPOINTS = [
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    ]

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        expected_limit: int = 60,
        endpoint: str = "/api/v1/auth/login",
        num_requests: int = None,
        verbose: bool = False,
        wait_time: float = 0,
        shared: bool = False
    ):
        self.base_url = base_url.rstrip('/')
        self.expected_limit = expected_limit
        self.endpoint = endpoint
        self.num_requests = num_requests or (expected_limit + 10)
        self.verbose = verbose
        self.wait_time = wait_time
        self.shared = shared
        self.results: List[Dict] = []
        self.endpoint_counts: Dict[str, int] = {}

    def print_header(self):
        """Print test configuration."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}Rate Limiting Test{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")

        print(f"{Colors.BOLD}Configuration:{Colors.END}")
        print(f"  API URL:           {Colors.BLUE}{self.base_url}{Colors.END}")

        if self.shared:
            print(f"  Test Mode:         {Colors.YELLOW}Shared (Multiple Endpoints){Colors.END}")
            print(f"  Endpoints:         {Colors.BLUE}{', '.join(self.SHARED_ENDPOINTS)}{Colors.END}")
        else:
            print(f"  Test Mode:         {Colors.YELLOW}Single Endpoint{Colors.END}")
            print(f"  Test Endpoint:     {Colors.BLUE}{self.endpoint}{Colors.END}")

        print(f"  Expected Limit:    {Colors.YELLOW}{self.expected_limit}{Colors.END} requests/minute")
        print(f"  Requests to Make:  {Colors.YELLOW}{self.num_requests}{Colors.END}")
        print(f"  Wait Time:         {Colors.YELLOW}{self.wait_time}{Colors.END} seconds")
        print(f"  Verbose Mode:      {Colors.YELLOW}{self.verbose}{Colors.END}")
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}\n")

    def make_request(self, request_num: int, endpoint: str = None) -> Dict:
        """Make a single request and record the result."""
        endpoint = endpoint or self.endpoint
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        # Track endpoint usage
        self.endpoint_counts[endpoint] = self.endpoint_counts.get(endpoint, 0) + 1

        try:
            # Prepare request data based on endpoint
            if endpoint == "/api/v1/auth/login":
                response = requests.post(
                    url,
                    json={"username": f"test_user_{request_num}", "password": "test_pass"},
                    timeout=5
                )
            elif endpoint == "/api/v1/auth/register":
                response = requests.post(
                    url,
                    json={
                        "username": f"testuser_{request_num}_{int(time.time())}",
                        "email": f"test{request_num}_{int(time.time())}@example.com",
                        "password": "testpass123"
                    },
                    timeout=5
                )
            elif endpoint == "/health":
                response = requests.get(url, timeout=5)
            else:
                response = requests.get(url, timeout=5)

            elapsed = time.time() - start_time

            result = {
                "request_num": request_num,
                "endpoint": endpoint,
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed * 1000, 2),
                "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "rate_limited": response.status_code == 429,
            }

            # Parse response
            try:
                result["response"] = response.json()
            except:
                result["response"] = response.text[:100]

            return result

        except requests.RequestException as e:
            return {
                "request_num": request_num,
                "endpoint": endpoint,
                "status_code": 0,
                "elapsed_ms": 0,
                "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "rate_limited": False,
                "error": str(e)
            }

    def run_test(self) -> Tuple[bool, str]:
        """Run the rate limiting test."""
        self.print_header()

        print(f"{Colors.BOLD}Starting test...{Colors.END}\n")

        rate_limited = False
        rate_limit_at = None

        for i in range(1, self.num_requests + 1):
            # Select endpoint for shared mode
            if self.shared:
                # Rotate through endpoints
                endpoint_idx = (i - 1) % len(self.SHARED_ENDPOINTS)
                endpoint = self.SHARED_ENDPOINTS[endpoint_idx]
            else:
                endpoint = None  # Use default

            result = self.make_request(i, endpoint)
            self.results.append(result)

            # Print progress
            if self.verbose or result["rate_limited"]:
                status_color = Colors.GREEN if result["status_code"] == 200 else \
                              Colors.RED if result["status_code"] == 429 else \
                              Colors.YELLOW

                endpoint_display = f" [{result['endpoint']}]" if self.shared else ""
                print(f"  [{result['timestamp']}] Request {i:3d}{endpoint_display}: "
                      f"{status_color}{result['status_code']}{Colors.END} "
                      f"({result['elapsed_ms']}ms)")

                if result["rate_limited"] and self.verbose:
                    retry_after = result.get("response", {}).get("data", {}).get("retry_after", "?")
                    print(f"    {Colors.RED}→ Rate limited! Retry after: {retry_after}s{Colors.END}")

            elif i % 10 == 0:
                print(f"  Completed {i}/{self.num_requests} requests...")

            # Check if rate limited
            if result["rate_limited"] and not rate_limited:
                rate_limited = True
                rate_limit_at = i
                if self.shared:
                    print(f"\n  {Colors.BOLD}{Colors.RED}✗ Rate limit triggered at request #{i} "
                          f"(endpoint: {result['endpoint']}){Colors.END}\n")
                else:
                    print(f"\n  {Colors.BOLD}{Colors.RED}✗ Rate limit triggered at request #{i}{Colors.END}\n")

            # Wait between requests if specified
            if self.wait_time > 0 and i < self.num_requests:
                time.sleep(self.wait_time)

        # Print summary
        self.print_summary(rate_limited, rate_limit_at)

        # Determine if test passed
        if rate_limited:
            if rate_limit_at <= self.expected_limit + 5:  # Allow small margin
                return True, f"Rate limit triggered at request #{rate_limit_at} (expected ~{self.expected_limit})"
            else:
                return False, f"Rate limit triggered too late at request #{rate_limit_at} (expected ~{self.expected_limit})"
        else:
            return False, f"Rate limit never triggered (made {self.num_requests} requests)"

    def print_summary(self, rate_limited: bool, rate_limit_at: int):
        """Print test summary."""
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}Test Summary{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")

        # Count status codes
        status_counts = {}
        for result in self.results:
            code = result["status_code"]
            status_counts[code] = status_counts.get(code, 0) + 1

        print(f"{Colors.BOLD}Response Status Codes:{Colors.END}")
        for code, count in sorted(status_counts.items()):
            color = Colors.GREEN if code == 200 else \
                   Colors.RED if code == 429 else \
                   Colors.YELLOW
            print(f"  {color}{code}{Colors.END}: {count} requests")

        # Show per-endpoint stats in shared mode
        if self.shared and self.endpoint_counts:
            print(f"\n{Colors.BOLD}Requests Per Endpoint:{Colors.END}")
            for endpoint, count in sorted(self.endpoint_counts.items()):
                print(f"  {Colors.BLUE}{endpoint}{Colors.END}: {count} requests")

        print(f"\n{Colors.BOLD}Rate Limiting:{Colors.END}")
        if rate_limited:
            print(f"  Status: {Colors.GREEN}✓ Rate limiting is WORKING{Colors.END}")
            print(f"  Triggered at: Request #{Colors.YELLOW}{rate_limit_at}{Colors.END}")
            print(f"  Expected: ~{Colors.YELLOW}{self.expected_limit}{Colors.END} requests/minute")

            # Calculate margin
            margin = abs(rate_limit_at - self.expected_limit)
            if margin <= 5:
                print(f"  Accuracy: {Colors.GREEN}Excellent (±{margin} requests){Colors.END}")
            elif margin <= 10:
                print(f"  Accuracy: {Colors.YELLOW}Good (±{margin} requests){Colors.END}")
            else:
                print(f"  Accuracy: {Colors.RED}Off by {margin} requests{Colors.END}")
        else:
            print(f"  Status: {Colors.RED}✗ Rate limiting NOT triggered{Colors.END}")
            print(f"  Made {self.num_requests} requests without hitting limit")

        # Performance stats
        if self.results:
            elapsed_times = [r["elapsed_ms"] for r in self.results if r["elapsed_ms"] > 0]
            if elapsed_times:
                avg_time = sum(elapsed_times) / len(elapsed_times)
                min_time = min(elapsed_times)
                max_time = max(elapsed_times)

                print(f"\n{Colors.BOLD}Performance:{Colors.END}")
                print(f"  Average response time: {Colors.YELLOW}{avg_time:.2f}ms{Colors.END}")
                print(f"  Min response time: {Colors.GREEN}{min_time:.2f}ms{Colors.END}")
                print(f"  Max response time: {Colors.RED}{max_time:.2f}ms{Colors.END}")

        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test rate limiting functionality of the PAT API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --limit 100 --verbose
  %(prog)s --endpoint /health
  %(prog)s --url http://example.com:8000 --limit 120
        """
    )

    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='API base URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=60,
        help='Expected rate limit per minute (default: 60)'
    )
    parser.add_argument(
        '--endpoint',
        default='/api/v1/auth/login',
        help='API endpoint to test (default: /api/v1/auth/login)'
    )
    parser.add_argument(
        '--requests',
        type=int,
        help='Number of requests to make (default: limit + 10)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output for each request'
    )
    parser.add_argument(
        '--wait',
        type=float,
        default=0,
        help='Wait time between requests in seconds (default: 0)'
    )
    parser.add_argument(
        '--shared',
        action='store_true',
        help='Test shared rate limiting across multiple endpoints'
    )

    args = parser.parse_args()

    # Create tester
    tester = RateLimitTester(
        base_url=args.url,
        expected_limit=args.limit,
        endpoint=args.endpoint,
        num_requests=args.requests,
        verbose=args.verbose,
        wait_time=args.wait,
        shared=args.shared
    )

    # Run test
    try:
        success, message = tester.run_test()

        if success:
            print(f"{Colors.BOLD}{Colors.GREEN}✓ TEST PASSED{Colors.END}: {message}\n")
            exit(0)
        else:
            print(f"{Colors.BOLD}{Colors.RED}✗ TEST FAILED{Colors.END}: {message}\n")
            exit(1)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test interrupted by user{Colors.END}\n")
        exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}\n")
        exit(1)


if __name__ == "__main__":
    main()
