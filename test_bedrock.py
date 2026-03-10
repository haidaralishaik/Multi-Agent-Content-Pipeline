"""
Test AWS Bedrock API connection
"""
import boto3
import json

# Initialize Bedrock client
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-east-1'
)

# Test with Claude 3.5 Haiku
model_id = 'us.anthropic.claude-3-5-haiku-20241022-v1:0'

# Prepare request
body = json.dumps({
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 100,
    "messages": [
        {
            "role": "user",
            "content": "Say 'Hello from AWS Bedrock!' and nothing else."
        }
    ]
})

# Call Bedrock
try:
    response = bedrock.invoke_model(
        modelId=model_id,
        body=body
    )
    
    # Parse response
    response_body = json.loads(response['body'].read())
    text = response_body['content'][0]['text']
    
    print("[OK] AWS Bedrock is working!")
    print(f"Response: {text}")
    
    # Show token usage
    usage = response_body['usage']
    print(f"\nTokens used:")
    print(f"  Input: {usage['input_tokens']}")
    print(f"  Output: {usage['output_tokens']}")
    
    # Calculate cost (Haiku pricing)
    input_cost = (usage['input_tokens'] / 1_000_000) * 0.80
    output_cost = (usage['output_tokens'] / 1_000_000) * 4.00
    total_cost = input_cost + output_cost
    
    print(f"\nCost: ${total_cost:.6f}")
    
except Exception as e:
    print(f"[ERROR] Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check AWS credentials: aws sts get-caller-identity")
    print("2. Verify Bedrock model access in console")
    print("3. Ensure region is us-east-1")