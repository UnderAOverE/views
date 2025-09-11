data = [
    {"id": "1", "name": "ABC-INT-ProjectX"},
    {"id": "2", "name": "GFD-INT-ProjectY"},
    {"id": "3", "name": "HJK-PROD-ServiceA"},
    {"id": "4", "name": "ABC-TEST-ComponentB"},
    {"id": "5", "name": "XYZ-DEV-FeatureC"},
    {"id": "6", "name": "GFD-UAT-ModuleD"},
    {"id": "7", "name": "LMN-INT-TaskE"},
    {"id": "8", "no_name_field": "oops"},
    {"id": "9", "name": "NO-HYPHEN"},
]

allowed_prefixes = {"GFD", "ABC"}

filtered_data_comprehension = [
    item for item in data
    if item.get("name") and item["name"].split('-')[0] in allowed_prefixes
]

print("Filtered Data (using list comprehension):")
for item in filtered_data_comprehension:
    print(item)

# Extract IDs from filtered_data_comprehension
filtered_ids = {item["id"] for item in filtered_data_comprehension}

# Example resources list
resources = [
    {"accountId": "1", "arn": "arn:aws:sqs:us-east-1:123456789012:queue1", "awsRegion": "us-east-1", "Name": "QueueA", "Endpoint": "sqs.us-east-1.amazonaws.com"},
    {"accountId": "2", "arn": "arn:aws:lambda:us-west-2:987654321098:function:func1", "awsRegion": "us-west-2", "Name": "LambdaB", "Endpoint": "lambda.us-west-2.amazonaws.com"},
    {"accountId": "3", "arn": "arn:aws:ec2:us-east-1:111122223333:instance/i-1234567890abcdef0", "awsRegion": "us-east-1", "Name": "EC2InstanceC", "Endpoint": "ec2.us-east-1.amazonaws.com"},
    {"accountId": "4", "arn": "arn:aws:s3:::my-bucket", "awsRegion": "us-east-1", "Name": "S3BucketD", "Endpoint": "s3.us-east-1.amazonaws.com"},
    {"accountId": "6", "arn": "arn:aws:dynamodb:eu-west-1:444455556666:table/MyTable", "awsRegion": "eu-west-1", "Name": "DynamoDBE", "Endpoint": "dynamodb.eu-west-1.amazonaws.com"},
    {"accountId": "10", "arn": "arn:aws:sns:us-east-1:000011112222:topic1", "awsRegion": "us-east-1", "Name": "SNSTopicF", "Endpoint": "sns.us-east-1.amazonaws.com"},
]

# Create a dictionary for quick lookup of data 'name' by 'id'
data_name_map = {item["id"]: item["name"] for item in filtered_data_comprehension}

final_resource_list = []
for resource in resources:
    account_id = resource.get("accountId")
    if account_id and account_id in filtered_ids:
        new_resource_entry = {
            "accountId": account_id,
            "arn": resource.get("arn"),
            "awsRegion": resource.get("awsRegion"),
            "Name": resource.get("Name"),
            "Endpoint": resource.get("Endpoint"),
            "account_name": data_name_map.get(account_id) # Get the 'name' from the original data
        }
        final_resource_list.append(new_resource_entry)

print("\nFinal Resource List:")
for item in final_resource_list:
    print(item)
