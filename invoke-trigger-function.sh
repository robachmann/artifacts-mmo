#!/bin/bash
source ./src/.env
aws lambda invoke --function-name artifacts-mmo-trigger-function --cli-binary-format raw-in-base64-out /dev/null --payload '{ "move_from_failure": true }' --profile $PROFILE_NAME
