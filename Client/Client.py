import requests
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

class APITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.all_tests_passed = True

    def test_endpoint(self, endpoint: str, expected_status: int = 200,
                      expected_data: Optional[Dict[str, Any]] = None,
                      error_message: str = "",
                      params: Optional[Dict[str, Any]] = None) -> bool:
        """Test an endpoint and print the result"""
        try:
            print(f"\nTesting {endpoint}...")
            if params:
                encoded_params = '&'.join(f"{key}={value}" for key, value in params.items())
                response = requests.get(f"{self.base_url}{endpoint}?{encoded_params}")
            else:
                response = requests.get(f"{self.base_url}{endpoint}")

            # Check status code
            if response.status_code != expected_status:
                print(f"❌ Failed: Expected status {expected_status}, got {response.status_code}")
                if error_message:
                    print(f"Hint: {error_message}")
                self.all_tests_passed = False
                return False

            # If we have expected data, check it
            if expected_data is not None:
                data = response.json()
                for key, value in expected_data.items():
                    if key not in data or data[key] != value:
                        print(f"❌ Failed: Expected {key}={value}, got {data.get(key, 'missing')}")
                        self.all_tests_passed = False
                        return False

            print("✅ Passed!")
            return True

        except requests.exceptions.ConnectionError:
            print("❌ Failed: Could not connect to server. Is it running?")
            self.all_tests_passed = False
            return False
        except Exception as e:
            print(f"❌ Failed: Unexpected error: {e}")
            self.all_tests_passed = False
            return False


def main():
    tester = APITester()
    print("Starting API tests...")
    print("Make sure your server is running on http://localhost:8000")
    print("Testing will begin in 3 seconds...")
    time.sleep(3)

    # Test root endpoint
    tester.test_endpoint(
        "/",
        expected_data={"message": "Welcome to the Twap-Trading-API"},
        error_message="The root endpoint should return a welcome message"
    )

    # Test exchanges endpoint
    tester.test_endpoint(
        "/exchanges",
        expected_data={"exchanges": ["Binance", "Bybit", "Coinbase", "Kucoin"]},
        error_message="The exchanges endpoint should return a list of all available exchanges"
    )

    # Test symbols endpoint
    tester.test_endpoint(
        "/Binance/symbols",
        error_message="The symbols endpoint should return a list of all available trading pairs"
    )

    # Test klines endpoint
    # Equivalent request on the Binance API would be :
    # https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime=1738368000000&endTime=1738371600000
    tester.test_endpoint(
        "/klines/Binance/BTCUSDT",
        expected_data= {
                          "klines": {
                            "2025-02-01T00:00:00": {
                              "Open": 102429.56,
                              "High": 102783.71,
                              "Low": 100279.51,
                              "Close": 100635.65,
                              "Volume": 12290.95747
                            }
                          }
                        },
        error_message="The klines endpoint should return a list of dictionaries with historical data",
        params={"interval": "1d", "start_time": "2025-02-01T00:00:00", "end_time": "2025-02-01T01:00:00"}
    )


if __name__ == "__main__":
    main()