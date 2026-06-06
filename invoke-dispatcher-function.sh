#!/bin/bash
source ./src/.env
aws lambda invoke --function-name artifacts-mmo-dispatcher-function --cli-binary-format raw-in-base64-out /dev/null --profile $PROFILE_NAME --region us-west-2
