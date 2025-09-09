
import boto3
from strands.models import BedrockModel




model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"

region_name = "us-west-2"





# Create a custom boto3 session
session = boto3.Session( # Optional: Use a specific profile
)

# Create a Bedrock model with the custom session
bedrock_model = BedrockModel(
    model_id=model_id,
    boto_session=session
)



transcribe_client = boto3.client('transcribe',region_name="us-west-2")

polly_client = boto3.client('polly',region_name='us-west-2')

