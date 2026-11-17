import os

from strands.models.bedrock import BedrockModel

# A fast, inexpensive model is enough for "turn a sentence into tool calls". Change it with an environment variable
# (CLOUDPAW_MODEL_ID) or by editing this line: the rest of the project does not care which model it is.
DEFAULT_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


def load_model() -> BedrockModel:
    """Bedrock model client using the IAM credentials of the environment (your profile locally, the role in AgentCore)."""
    return BedrockModel(
        model_id=os.getenv("CLOUDPAW_MODEL_ID", DEFAULT_MODEL_ID),
        region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
        temperature=0.0,  # commands to a robot should not be creative
    )
