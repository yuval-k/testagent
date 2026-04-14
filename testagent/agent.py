import argparse
import os
import random
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools import tool
from strands.tools.mcp import MCPClient


DEFAULT_AWS_REGION = "us-west-2"
DEFAULT_MODEL_NAME = "us.amazon.nova-lite-v1:0"
DEFAULT_AGENTCORE_RUNTIME_ARN = (
    "arn:aws:bedrock-agentcore:us-west-2:802411188784:runtime/yuval_kechomcp-NWSkxf7ZhI"
)

ROLL_HISTORY: list[int] = []
SYSTEM_PROMPT = """
You roll dice and answer questions about the outcome of the dice rolls.
You can roll dice of different sizes.
It is ok to discuss previous dice rolls and comment on them.
When you are asked to roll a die, you must call the roll_die tool with the number of sides.
Be sure to pass an integer, never a string.
You should never roll a die on your own.
When checking prime numbers, call the check_prime tool with a list of integers.
Be sure to pass a list of integers, never a string.
You should not check prime numbers before calling the tool.
When you are asked to roll a die and check prime numbers, follow this order:
1. Call roll_die first and wait for the result.
2. Call check_prime with the roll_die result after you receive it.
3. Include the roll_die result in your response.
If the user asks you to check primes based on previous rolls, include the previous rolls in the list.
Do not rely on prior prime-number outputs.
"""


@tool
def roll_die(sides: int) -> int:
    """Roll a die and record the outcome for later reference."""
    result = random.randint(1, sides)
    ROLL_HISTORY.append(result)
    return result


@tool
def check_prime(nums: list[int]) -> str:
    """Check whether the provided numbers are prime."""
    primes = set()
    for number in nums:
        if number <= 1:
            continue

        is_prime = True
        for i in range(2, int(number**0.5) + 1):
            if number % i == 0:
                is_prime = False
                break

        if is_prime:
            primes.add(number)

    if not primes:
        return "No prime numbers found."
    return f"{', '.join(str(num) for num in sorted(primes))} are prime numbers."


def get_aws_region() -> str:
    return os.environ.get("AWS_REGION", DEFAULT_AWS_REGION)


def get_model_name() -> str:
    return os.environ.get("MODEL_NAME", DEFAULT_MODEL_NAME)


def get_agentcore_runtime_arn() -> str:
    return os.environ.get("AGENTCORE_RUNTIME_ARN", DEFAULT_AGENTCORE_RUNTIME_ARN)


def build_agentcore_endpoint() -> str:
    encoded_runtime_arn = quote(get_agentcore_runtime_arn(), safe="")
    return (
        f"https://bedrock-agentcore.{get_aws_region()}.amazonaws.com/"
        f"runtimes/{encoded_runtime_arn}/invocations?qualifier=DEFAULT"
    )


def create_model() -> BedrockModel:
    return BedrockModel(
        model_id=get_model_name(),
        region_name=get_aws_region(),
    )


def create_mcp_client() -> MCPClient:
    return MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=build_agentcore_endpoint(),
            aws_service="bedrock-agentcore",
            aws_region=get_aws_region(),
        )
    )


def build_agent(mcp_client: MCPClient) -> Agent:
    return Agent(
        model=create_model(),
        tools=[roll_die, check_prime, mcp_client],
        system_prompt=SYSTEM_PROMPT,
        name="testagent",
        description="testagent agent.",
    )


def extract_text(result: Any) -> str:
    content_blocks = result.message.get("content", [])
    text_parts = [block["text"] for block in content_blocks if "text" in block]
    return "\n".join(text_parts).strip()


@asynccontextmanager
async def lifespan(app: BedrockAgentCoreApp):
    mcp_client = create_mcp_client()
    app.state.mcp_client = mcp_client
    app.state.mcp_client.start()
    try:
        yield
    finally:
        app.state.mcp_client.stop(None, None, None)


app = BedrockAgentCoreApp(lifespan=lifespan)


@app.entrypoint
def invoke(payload: dict[str, Any]) -> dict[str, str]:
    prompt = payload.get("prompt")
    if not prompt:
        raise ValueError("No prompt found in payload.")

    agent = build_agent(app.state.mcp_client)
    result = agent(prompt)
    # return {"text": extract_text(result)}
    return {"result": result.message}

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the testagent Strands AgentCore app.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    app.run(port=args.port, host=args.host)


if __name__ == "__main__":
    main()
