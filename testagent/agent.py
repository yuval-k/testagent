import random
import os

from google.adk import Agent
import traceback
from google.adk.tools.tool_context import ToolContext
from urllib.parse import quote

from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp import MCPClient

from .mcp_tools import get_mcp_tools

# Initialize OpenTelemetry
# Set service name from environment variable for OpenTelemetry
os.environ.setdefault('OTEL_SERVICE_NAME', 'testagent')

from google.adk.telemetry.setup import maybe_set_otel_providers
maybe_set_otel_providers()

DEFAULT_AWS_REGION = "us-west-2"
DEFAULT_MODEL_NAME = "us.amazon.nova-lite-v1:0"
DEFAULT_AGENTCORE_RUNTIME_ARN = (
    "arn:aws:bedrock-agentcore:us-west-2:802411188784:runtime/yuval_kechomcp-NWSkxf7ZhI"
)


def roll_die(sides: int, tool_context: ToolContext) -> int:
    """Roll a die and record the outcome for later reference."""
    result = random.randint(1, sides)
    if "rolls" not in tool_context.state:
        tool_context.state["rolls"] = []

    tool_context.state["rolls"] = tool_context.state["rolls"] + [result]
    return result

def get_agentcore_runtime_arn() -> str:
    return os.environ.get("AGENTCORE_RUNTIME_ARN", DEFAULT_AGENTCORE_RUNTIME_ARN)

def get_aws_region() -> str:
    return os.environ.get("AWS_REGION", DEFAULT_AWS_REGION)

def build_agentcore_endpoint() -> str:
    encoded_runtime_arn = quote(get_agentcore_runtime_arn(), safe="")
    return (
        f"https://bedrock-agentcore.{get_aws_region()}.amazonaws.com/"
        f"runtimes/{encoded_runtime_arn}/invocations?qualifier=DEFAULT"
    )

def exception_to_string(e):
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))

def tell_a_joke() -> int:
    """Tell a joke for your delight."""
    mcp_client = MCPClient(lambda: aws_iam_streamablehttp_client(
        endpoint=build_agentcore_endpoint(),
        aws_region=get_aws_region(),
        aws_service="bedrock-agentcore"
    ))
    with mcp_client:
        try:
            result = mcp_client.call_tool_sync(
                tool_use_id="tool-123",
                name="echo",
                arguments={"message":"hello world"},
            )
            return result
        except Exception as e:
            print(f"Error occurred while telling a joke: {e}")
            traceback.print_exception(type(e), e, e.__traceback__)
            return {"error": exception_to_string(e)}

async def check_prime(nums: list[int]) -> str:
    """Check whether the provided numbers are prime."""
    primes = set()
    for number in nums:
        number = int(number)
        if number <= 1:
            continue
        is_prime = True
        for i in range(2, int(number**0.5) + 1):
            if number % i == 0:
                is_prime = False
                break
        if is_prime:
            primes.add(number)
    return "No prime numbers found." if not primes else f"{', '.join(str(num) for num in primes)} are prime numbers."



def create_model():
    """Use a Gemini model."""
    return "gemini-2.0-flash"



mcp_tools = get_mcp_tools()
root_agent = Agent(
    model=create_model(),
    name="testagent_agent",
    description="testagent agent.",
    instruction="""
You roll dice and answer questions about the outcome of the dice rolls.
You can roll dice of different sizes.
You can use multiple tools in parallel by calling functions in parallel (in one request and in one round).
It is ok to discuss previous dice roles, and comment on the dice rolls.
When you are asked to roll a die, you must call the roll_die tool with the number of sides. Be sure to pass in an integer. Do not pass in a string.
You should never roll a die on your own.
When checking prime numbers, call the check_prime tool with a list of integers. Be sure to pass in a list of integers. You should never pass in a string.
You should not check prime numbers before calling the tool.
When you are asked to roll a die and check prime numbers, you should always make the following two function calls:
1. You should first call the roll_die tool to get a roll. Wait for the function response before calling the check_prime tool.
2. After you get the function response from roll_die tool, you should call the check_prime tool with the roll_die result.
2.1 If user asks you to check primes based on previous rolls, make sure you include the previous rolls in the list.
3. When you respond, you must include the roll_die result from step 1.
You should always perform the previous 3 steps when asking for a roll and checking prime numbers.
You should not rely on the previous history on prime results.


    """,
    tools=[
        tell_a_joke
    ],
)

