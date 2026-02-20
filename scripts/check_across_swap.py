#!/usr/bin/env python3
"""Check token support and active providers in Across Swap API.

This script is intentionally defensive because Across swap parameters/response
can evolve over time. It tries common parameter names and detects provider
mentions recursively in the JSON response.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_ENDPOINT = "https://app.across.to/api/swap/quote"
DEFAULT_FROM_CHAIN_ID = 1
DEFAULT_TO_CHAIN_ID = 1
DEFAULT_AMOUNT = "1000000000000000000"  # 1 token in wei-like units
DEFAULT_WALLET = "0x000000000000000000000000000000000000dEaD"

PROVIDERS = ["uniswap", "0x", "lifi"]

# Requested token list + practical fallback Ethereum addresses.
TOKENS: dict[str, str] = {
    "BAL": "0xba100000625a3754423978a60c9317c58a424e3D",
    "VLR": "0x0000000000000000000000000000000000000000",  # unknown/unset
    "POOL": "0x0cec1a9154ff802e7934fc916ed7ca50bde6844e",
    "LSK": "0x0000000000000000000000000000000000000000",  # unknown/unset
    "WLD": "0x163f8c2467924be0ae7b5347228cabf260318753",
    "WGHO": "0x0000000000000000000000000000000000000000",  # unknown/unset
    "CAKE": "0x152649ea73beab28c5b49b26eb48f7ead6d4c898",
    "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f",
    "SNX": "0xC011A73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F",
}

QUOTE_TARGET_TOKEN = TOKENS["DAI"]


@dataclass
class ProbeResult:
    token: str
    address: str
    supported: bool
    providers: list[str]
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Across Swap API token support probe")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--from-chain-id", type=int, default=DEFAULT_FROM_CHAIN_ID)
    parser.add_argument("--to-chain-id", type=int, default=DEFAULT_TO_CHAIN_ID)
    parser.add_argument("--amount", default=DEFAULT_AMOUNT)
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args()


def call_api(endpoint: str, params: dict[str, str], timeout: int) -> tuple[int, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{endpoint}?{query}"
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
        try:
            return response.status, json.loads(payload)
        except json.JSONDecodeError:
            return response.status, payload


def find_provider_mentions(obj: Any) -> set[str]:
    found: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                low_key = str(key).lower()
                if "provider" in low_key or "dex" in low_key or "source" in low_key:
                    text = str(value).lower()
                    for candidate in PROVIDERS:
                        if candidate in text:
                            found.add(candidate)
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)
        else:
            text = str(node).lower()
            for candidate in PROVIDERS:
                if candidate in text:
                    found.add(candidate)

    visit(obj)
    return found


def probe_provider(
    endpoint: str,
    token_in: str,
    token_out: str,
    provider: str,
    from_chain_id: int,
    to_chain_id: int,
    amount: str,
    wallet: str,
    timeout: int,
) -> tuple[bool, str, set[str]]:
    # Try a few common param naming variants.
    param_sets = [
        {
            "fromChainId": str(from_chain_id),
            "toChainId": str(to_chain_id),
            "tokenIn": token_in,
            "tokenOut": token_out,
            "amount": amount,
            "user": wallet,
            "swapProvider": provider,
        },
        {
            "originChainId": str(from_chain_id),
            "destinationChainId": str(to_chain_id),
            "inputToken": token_in,
            "outputToken": token_out,
            "inputAmount": amount,
            "recipient": wallet,
            "provider": provider,
        },
        {
            "chainId": str(from_chain_id),
            "fromToken": token_in,
            "toToken": token_out,
            "amount": amount,
            "account": wallet,
            "dexProvider": provider,
        },
    ]

    last_error = "no request executed"
    for params in param_sets:
        try:
            status, body = call_api(endpoint, params, timeout)
            mentions = find_provider_mentions(body)
            if isinstance(body, dict) and body.get("error"):
                last_error = f"HTTP {status}: {body.get('error')}"
                continue
            if status == 200:
                return True, "ok", mentions
            last_error = f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    return False, last_error, set()


def main() -> None:
    args = parse_args()
    results: list[ProbeResult] = []

    for symbol, address in TOKENS.items():
        if address.lower() == "0x0000000000000000000000000000000000000000":
            results.append(
                ProbeResult(
                    token=symbol,
                    address=address,
                    supported=False,
                    providers=[],
                    notes="missing token address; update TOKENS map",
                )
            )
            continue

        token_out = QUOTE_TARGET_TOKEN if symbol != "DAI" else TOKENS["SNX"]

        working_providers: list[str] = []
        discovered_providers: set[str] = set()
        errors: list[str] = []

        for provider in PROVIDERS:
            ok, note, mentions = probe_provider(
                endpoint=args.endpoint,
                token_in=address,
                token_out=token_out,
                provider=provider,
                from_chain_id=args.from_chain_id,
                to_chain_id=args.to_chain_id,
                amount=args.amount,
                wallet=args.wallet,
                timeout=args.timeout,
            )
            discovered_providers |= mentions
            if ok:
                working_providers.append(provider)
            else:
                errors.append(f"{provider}: {note}")

        supported = len(working_providers) > 0
        notes = (
            "providers with successful quote: " + ", ".join(working_providers)
            if supported
            else "; ".join(errors)
        )
        if discovered_providers:
            notes += f" | provider mentions in payload: {', '.join(sorted(discovered_providers))}"

        results.append(
            ProbeResult(
                token=symbol,
                address=address,
                supported=supported,
                providers=working_providers,
                notes=notes,
            )
        )

    print("Across Swap API support report")
    print("=" * 80)
    for item in results:
        providers = ", ".join(item.providers) if item.providers else "none"
        print(
            f"{item.token:>5} | supported={str(item.supported):<5} | providers={providers:<18} | {item.notes}"
        )


if __name__ == "__main__":
    main()
