#!/usr/bin/env python3
"""
Script to download historical OHLCV data from exchanges for backtesting.

Usage:
    python scripts/download_historical_data.py --symbol ETH/USDT --exchange binance --timeframes 1d,4h,1h,15m,5m
    python scripts/download_historical_data.py --all  # Download from all exchanges, all timeframes
"""

import argparse
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import ccxt


class HistoricalDataDownloader:
    """Download historical OHLCV data from cryptocurrency exchanges."""

    def __init__(self, output_dir: str = "data/historical"):
        """
        Initialize downloader.

        Args:
            output_dir: Directory to save downloaded data
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize exchanges
        self.exchanges = {
            "binance": ccxt.binance(),
            "bybit": ccxt.bybit(),
        }

        # CCXT timeframe mapping
        self.timeframe_map = {
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
            "m5": "5m",  # Alternative notation
            "m15": "15m",
            "h1": "1h",
            "h4": "4h",
            "d1": "1d",
        }

    def download_data(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[list]:
        """
        Download OHLCV data from exchange.

        Args:
            exchange_id: Exchange name (binance, bybit)
            symbol: Trading pair (e.g., ETH/USDT)
            timeframe: Candle timeframe (5m, 15m, 1h, 4h, 1d)
            start_date: Start date for data (default: 6 months ago)
            end_date: End date for data (default: now)
            limit: Max candles per request

        Returns:
            List of OHLCV candles [timestamp, open, high, low, close, volume]
        """
        if exchange_id not in self.exchanges:
            raise ValueError(f"Exchange {exchange_id} not supported")

        exchange = self.exchanges[exchange_id]

        # Normalize timeframe
        timeframe = self.timeframe_map.get(timeframe.lower(), timeframe)

        # Default date range: 6 months
        if not start_date:
            start_date = datetime.now() - timedelta(days=180)
        if not end_date:
            end_date = datetime.now()

        print(
            f"\n📥 Downloading {symbol} {timeframe} data from {exchange_id.upper()}..."
        )
        print(f"   Period: {start_date.date()} to {end_date.date()}")

        # Convert dates to timestamps
        since = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)

        all_candles = []
        current_timestamp = since

        try:
            while current_timestamp < end_timestamp:
                # Fetch candles
                candles = exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=current_timestamp,
                    limit=limit,
                )

                if not candles:
                    print(f"   ⚠️  No more data available")
                    break

                all_candles.extend(candles)

                # Update timestamp for next batch
                current_timestamp = candles[-1][0] + 1

                print(
                    f"   ✓ Downloaded {len(candles)} candles "
                    f"(total: {len(all_candles)}, "
                    f"latest: {datetime.fromtimestamp(candles[-1][0] / 1000).date()})"
                )

                # Rate limiting
                time.sleep(exchange.rateLimit / 1000)

                # Stop if we've reached the end date
                if candles[-1][0] >= end_timestamp:
                    break

        except ccxt.NetworkError as e:
            print(f"   ❌ Network error: {e}")
        except ccxt.ExchangeError as e:
            print(f"   ❌ Exchange error: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")

        print(f"   ✅ Downloaded {len(all_candles)} total candles")
        return all_candles

    def save_to_csv(
        self,
        candles: list[list],
        exchange_id: str,
        symbol: str,
        timeframe: str,
    ) -> Path:
        """
        Save OHLCV data to CSV file.

        Args:
            candles: List of OHLCV candles
            exchange_id: Exchange name
            symbol: Trading pair
            timeframe: Timeframe

        Returns:
            Path to saved CSV file
        """
        # Create filename
        symbol_safe = symbol.replace("/", "_")
        filename = f"{exchange_id}_{symbol_safe}_{timeframe}.csv"
        filepath = self.output_dir / filename

        # Write to CSV
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(["timestamp", "datetime", "open", "high", "low", "close", "volume"])

            # Data
            for candle in candles:
                timestamp = candle[0]
                dt = datetime.fromtimestamp(timestamp / 1000).isoformat()
                writer.writerow([timestamp, dt] + candle[1:])

        print(f"   💾 Saved to: {filepath}")
        return filepath

    def download_and_save(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[Path]:
        """
        Download data and save to CSV.

        Args:
            exchange_id: Exchange name
            symbol: Trading pair
            timeframe: Timeframe
            start_date: Start date
            end_date: End date

        Returns:
            Path to saved file or None if failed
        """
        try:
            # Download
            candles = self.download_data(
                exchange_id=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
            )

            if not candles:
                print(f"   ⚠️  No data downloaded")
                return None

            # Save
            filepath = self.save_to_csv(
                candles=candles,
                exchange_id=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
            )

            return filepath

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None

    def download_all_timeframes(
        self,
        exchange_id: str,
        symbol: str,
        timeframes: list[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict[str, Optional[Path]]:
        """
        Download data for multiple timeframes.

        Args:
            exchange_id: Exchange name
            symbol: Trading pair
            timeframes: List of timeframes
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping timeframe to file path
        """
        results = {}

        for timeframe in timeframes:
            filepath = self.download_and_save(
                exchange_id=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
            )
            results[timeframe] = filepath

        return results

    def download_all_exchanges(
        self,
        symbol: str,
        timeframes: list[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict[str, dict[str, Optional[Path]]]:
        """
        Download data from all exchanges.

        Args:
            symbol: Trading pair
            timeframes: List of timeframes
            start_date: Start date
            end_date: End date

        Returns:
            Nested dict: exchange -> timeframe -> file path
        """
        results = {}

        for exchange_id in self.exchanges.keys():
            print(f"\n{'='*60}")
            print(f"Exchange: {exchange_id.upper()}")
            print(f"{'='*60}")

            results[exchange_id] = self.download_all_timeframes(
                exchange_id=exchange_id,
                symbol=symbol,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date,
            )

        return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download historical OHLCV data from exchanges"
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default="ETH/USDT",
        help="Trading pair (default: ETH/USDT)",
    )

    parser.add_argument(
        "--exchange",
        type=str,
        choices=["binance", "bybit", "all"],
        default="all",
        help="Exchange to download from (default: all)",
    )

    parser.add_argument(
        "--timeframes",
        type=str,
        default="1d,4h,1h,15m,5m",
        help="Comma-separated timeframes (default: 1d,4h,1h,15m,5m)",
    )

    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD), default: 6 months ago",
    )

    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD), default: today",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/historical",
        help="Output directory (default: data/historical)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all: both exchanges, all timeframes for ETH/USDT",
    )

    args = parser.parse_args()

    # Parse dates
    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

    # Parse timeframes
    timeframes = [tf.strip() for tf in args.timeframes.split(",")]

    # Initialize downloader
    downloader = HistoricalDataDownloader(output_dir=args.output_dir)

    print("="*60)
    print("📊 Historical Data Downloader")
    print("="*60)
    print(f"Symbol: {args.symbol}")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Output directory: {args.output_dir}")
    print("="*60)

    # Download
    if args.all or args.exchange == "all":
        # Download from all exchanges
        results = downloader.download_all_exchanges(
            symbol=args.symbol,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        # Download from single exchange
        results = downloader.download_all_timeframes(
            exchange_id=args.exchange,
            symbol=args.symbol,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
        )

    # Summary
    print("\n" + "="*60)
    print("✅ Download Complete!")
    print("="*60)

    total_files = 0
    if args.all or args.exchange == "all":
        for exchange_id, timeframe_results in results.items():
            successful = sum(1 for path in timeframe_results.values() if path)
            total_files += successful
            print(f"{exchange_id.upper()}: {successful}/{len(timeframe_results)} files")
    else:
        successful = sum(1 for path in results.values() if path)
        total_files = successful
        print(f"{args.exchange.upper()}: {successful}/{len(results)} files")

    print(f"\nTotal files downloaded: {total_files}")
    print(f"Location: {downloader.output_dir.absolute()}")


if __name__ == "__main__":
    main()
