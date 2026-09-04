# Alpaca AI Trading Agents Hackathon Submission

This repository now includes a runnable paper-only options-agent demo in
`examples/paper-options-agent/`. Complete the evidence fields below before
submitting; do not replace a pending item with an invented URL or account ID.

> **Submission status:** The code, safety controls, documentation, and tests are
> complete. The remaining pending items require the owner's Alpaca account and
> published media; they cannot be generated safely from this repository.

## Required evidence

| Submission item | Evidence |
|---|---|
| Public repository | **PENDING — owner adds the final public repository URL** |
| Runnable demo instructions | [`examples/paper-options-agent/README.md`](examples/paper-options-agent/README.md) |
| Paper account ID | **PENDING — owner adds a redacted identifier after account setup** |
| Live demo URL | **PENDING — add a working public URL if the submission requires one** |
| Demo video | **PENDING — owner publishes and adds the final video URL** |
| Slide deck | **PENDING — owner publishes and adds the final slide URL** |
| Cover image | **PENDING — owner publishes and adds the final image URL** |
| Hackathon write-up | **PENDING — owner publishes and adds the final write-up URL** |
| Social posts | **PENDING — add links only after publishing** |

## Demo acceptance checklist

- [ ] Run the local unit tests.
- [ ] Create or reset a dedicated Alpaca paper account with the required
  $100,000 starting balance.
- [ ] Verify options level 2 or higher in the account.
- [ ] Run the dry-run command and capture the JSON preview.
- [ ] Show the hard paper endpoint and risk configuration.
- [ ] Submit at most one order with `--submit` and capture its paper order ID.
- [ ] Demonstrate the duplicate-order gate with a second invocation.
- [ ] Keep API keys, secrets, and unredacted account identifiers out of the
  video, screenshots, repository, and write-up.
- [ ] Include the paper-trading and options disclosures in the presentation and
  written submission.

## What the demo proves

The agent is not presented as a profitable strategy. The demonstrable claims
are narrower and reproducible: an AI host can explain and operate the skill,
while the runner reads completed Alpaca bars and indicative option data,
detects a defined signal, validates paper-account readiness, selects an option
under explicit liquidity and expiration constraints, previews the full order,
and uses a deterministic client order ID before any paper submission.
