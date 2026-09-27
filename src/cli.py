#!/usr/bin/env python3
"""
CLI entry point for Solana DeFi Analytics.
"""
import argparse
import asyncio
import logging

from src.engines.slippage import compare_routes
from src.utils import setup_logging


def setup_cli_logging():
    setup_logging(logging.INFO)

async def async_main(args):
    if args.command == 'quote':
        # Load config for RPC? Not needed for quote.
        df = await compare_routes(args.token_in, args.token_out, args.amount)
        if df.empty:
            print("No routes found.")
        else:
            print(df.to_string(index=False))
    else:
        print("Unknown command")

def main():
    parser = argparse.ArgumentParser(description="Solana DeFi Analytics CLI")
    subparsers = parser.add_subparsers(dest='command', required=True)

    quote_parser = subparsers.add_parser('quote', help='Get swap quote and route comparison')
    quote_parser.add_argument('token_in', help='Input token mint address')
    quote_parser.add_argument('token_out', help='Output token mint address')
    quote_parser.add_argument('amount', type=float, help='Amount of input token in natural units (e.g., SOL)')

    args = parser.parse_args()
    setup_cli_logging()
    asyncio.run(async_main(args))

if __name__ == '__main__':
    main()
