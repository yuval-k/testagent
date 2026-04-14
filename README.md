# Test Agent

This repo now runs a Strands-based HTTP agent service instead of ADK.

It exposes:
- `GET /ping`
- `POST /invocations`

The agent uses:
- Amazon Bedrock for the model, via IAM credentials
- an AgentCore MCP runtime over AWS IAM using `mcp-proxy-for-aws`
- two local tools: `roll_die` and `check_prime`

Run locally with `uv`:

```bash
uv sync
uv run testagent --local
```

Invoke it:

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"input":{"prompt":"roll a 20 sided die and tell me if it is prime"}}'
```
