# At a glance

Welcome and thank you for your interest in this client to play [Artifacts](https://www.artifactsmmo.com/).

## Support this project

If you find this project useful and want to support ongoing development, you can buy me a coffee on Ko-fi.

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/rbac3555)

# Prerequisites

1. Artifacts account → https://artifactsmmo.com/account/register
2. AWS account → https://aws.amazon.com/
3. Telegram bot → https://telegram.me/BotFather

Optional:

4. Artifacts subscription to consume websocket (recommended) → https://docs.artifactsmmo.com/funding
5. Prometheus/Grafana stack to display metrics

# Architecture

This client utilizes a serverless architecture based on a variety of AWS services:

- AWS Lambda to process and apply the business logic of the client
- Amazon SQS to schedule process steps based on a character's cooldown
- Amazon DynamoDB to store current task list, bank reservations and statistics
- Amazon SNS to process the game's log events
- Amazon API Gateway to expose APIs for Telegram, webhook events and a metrics endpoint
- Amazon ECS to subscribe to websocket events (optional, requires Artifacts subscription)
- Amazon S3 to persist metrics
- Amazon CloudWatch to store this application's logs

## Local alternative for websocket (optional)

Instead of running an ECS container to listen to websocket events and forward them to the API gateway endpoint, you can
deploy the prebuilt image on any other container orchestrator, for example Portainer, to save on
costs. You can find the image here: https://hub.docker.com/r/robachmann/artifactsmmo-websocket-container.
This container requires these environment variables to be set:

| Variable              | Description                                            | Mandatory | Default Value                     |
|-----------------------|--------------------------------------------------------|-----------|-----------------------------------|
| PLAYER_TOKEN          | Player's API Token                                     | Yes       | -                                 |
| WEBHOOK_URL           | Target endpoint to send received websocket message to  | Yes       | -                                 |
| SUBSCRIPTIONS         | Check `subscriptions.txt` for possible values.         | Yes       | -                                 |
| WEBSOCKET_URL         | Source endpoint to receive websocket messages from     | No        | `wss://realtime.artifactsmmo.com` |
| LOG_TEST_MESSAGES     | Flag to log received websocket messages of type `test` | No        | `false`                           |
| SKIP_SSL_VERIFICATION | Flag to skip SSL verification of websocket server      | No        | `false`                           |

## Running cost

Deploying this application will incur an average of 5-15 USD per month - depending on the selected region and deployed
parts.

# Local execution

Classes and files in `src/local-functions` are meant for local execution and will not be deployed. This way, code can be
safely tested. Most often, you will use it to find suitable combat configurations and plan your strategy.

# Deployment

1. Ensure `.aws/config` contains the profile specified in `src/.env`
2. Configure values in `samconfig.yml`, especially the SubnetId parameter
3. `./deploy.sh`
4. Update Telegram webhook
5. Prometheus:
    1. Update prometheus.yaml
    2. `http POST <prometheus-server>:9090/-/reload`

## Disclaimer

This is a hobby project provided "as is", without warranty of any kind. The author(s) assume no responsibility or
liability for any misconfigurations, bugs, security issues, data loss, or costs incurred from deploying or using this
software, including but not limited to AWS charges. Use at your own risk.

# Configuration

All instructions for your characters are captured in the dispatcher function (`src/dispatcher-function`):

| File                | Dispatch Order | Purpose                                                                                                                                                                             |
|---------------------|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| event_priorities.py | 1              | Let's you specify which characters will participate in occasionally spawning events. <br/>If two events are active at the same time, the order of the list determines the priority. |
| quest_leaders.py    | 2              | This is the configuration for the main character(s), so called quest leaders. If other characters can, they will join the quest leader to solve their quests.                       |
| single_quests.py    | 3              | Characters which cannot contribute to the quests of others will get their orders from this file.                                                                                    |
| trade_limits.py     |                | Configuration of items to buy from and sell to NPCs.                                                                                                                                | 

# Development

# Todos and roadmap

There are currently no hot topics to address. Minor optimizations are implemented regularly.

# Useful Cloud Watch Logs Insights queries

[Link](https://eu-central-2.console.aws.amazon.com/cloudwatch/home?logsV2%3Alogs-insights=&region=eu-central-2#logsV2:logs-insights)

### Get all non-info logs

```
fields @timestamp, message_id, level, character_name, quest_id, task_id, kind, action, message
| filter @type not in ['START', 'REPORT', 'END']
| filter @message not like /INIT_START.+/
#| filter action not in ['fight', 'gather']
| filter level not in ['INFO']
#| filter character_name = ''
#| filter isempty(character_name)
| sort @timestamp desc
| limit 1000
```

### Get logs

```
fields @timestamp, message_id, level, character_name, quest_id, task_id, kind, action, message
| filter @type not in ['START', 'REPORT', 'END']
| filter @message not like /INIT_START.+/
#| filter action not in ['fight', 'gather']
#| filter level not in ['INFO']
#| filter character_name = ''
#| filter isempty(character_name)
| sort @timestamp desc
| limit 1000
```

### Get all logs of character

```
fields @timestamp, message_id, level, character_name, quest_id, task_id, kind, action, message
| filter @type not in ['START', 'REPORT', 'END']
| filter @message not like /INIT_START.+/
| filter action not in ['fight', 'equip', 'unequip', 'withdraw', 'deposit', 'rest', 'move', 'use-item']
#| filter level not in ['INFO']
| filter character_name not in ['Fox_2', 'Fox_3', 'Fox_1', 'Fox_4']
#| filter character_name = ''
| filter not isempty(action)
| sort @timestamp desc
| limit 1000
```

### Get all logs of websocket container

```
fields @timestamp, @message
| sort @timestamp desc
| limit 1000
```

### Get all non-info logs

```
fields @timestamp, message_id, level, character_name, kind, action, message, @logStream
| filter @type not in ['START', 'REPORT', 'END']
| filter @message not like /INIT_START.+/
| filter level not in ['INFO']
#| filter character_name = ''
| sort @timestamp desc
| limit 1000
```

### Get all errors

```
fields @timestamp, @message, @logStream
| filter @type not in ['START', 'REPORT', 'END']
| filter @message not like /INIT_START.+/
| filter isempty(character_name)
| sort @timestamp desc
| limit 1000
```

## Local development with Powertools

`pip install "aws-lambda-powertools[aws-sdk]"`

## Example Prometheus config

```
- job_name: 'artifacts-mmo'
  scheme: https
  metrics_path: '/prod/metrics/metrics.prom'
  scrape_interval: '5m'
  static_configs:
    - targets: ['<resource-name>.execute-api.<region>.amazonaws.com']
```
