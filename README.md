# Across Swap API checker (beginner friendly)

This repository contains a small Python script that helps you check if specific tokens are supported by the Across Swap API and which provider is serving the quote (`uniswap`, `0x`, or `lifi`).

## What this checks

For each token symbol in this list:

- BAL
- VLR
- POOL
- LSK
- WLD
- WGHO
- CAKE
- DAI
- SNX

the script:

1. Builds quote requests to the Across Swap API.
2. Tries each provider (`uniswap`, `0x`, `lifi`).
3. Reports:
   - whether the token appears supported (successful response), and
   - which provider returned a success.

## Important note

In this execution environment, outbound access to Across/GitHub endpoints was blocked (HTTP 403 tunnel errors), so the API call could not be validated live here.

The script is still written to run from your own computer with internet access.

## Prerequisites

- Python 3.10+

## Run it

```bash
python scripts/check_across_swap.py
```

Optional flags:

```bash
python scripts/check_across_swap.py \
  --endpoint "https://app.across.to/api/swap/quote" \
  --from-chain-id 1 \
  --to-chain-id 1
```

## Output example

The script prints one line per token with status and providers that worked.

## Token addresses

The script includes known/fallback Ethereum addresses for the requested symbols.
If needed, you can edit the `TOKENS` dictionary in `scripts/check_across_swap.py`.
