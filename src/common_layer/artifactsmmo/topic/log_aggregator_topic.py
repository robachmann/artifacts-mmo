import os
from artifactsmmo.log.logger import logger
import boto3


class LogAggregatorPublisher:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            self.is_cloud = False
        else:
            self.is_cloud = True
            self.topic_arn = os.environ.get('LOG_AGGREGATOR_TOPIC_ARN')
            self.sns = boto3.client('sns')

    def invoke_log_aggregator(self, character_name: str):
        if self.is_cloud:
            if self.topic_arn:
                self.sns.publish(
                    TopicArn=self.topic_arn,
                    Message=character_name,
                )
            else:
                logger.error(f'topic_arn is not set: {os.environ.get("LOG_AGGREGATOR_TOPIC_ARN")}')
