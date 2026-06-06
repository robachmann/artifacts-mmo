#!/bin/bash
source ./src/.env
http POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setMyCommands" < telegram-commands.json