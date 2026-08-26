#!/bin/bash
if [ "$1" = "--version" ]; then
    echo "qmd mock version"
elif [[ "$*" == *"query"* && "$*" == *"--format json"* ]]; then
    echo '{"results": [{"file": "exchange123/references/mailbox.md", "score": 0.95}]}'
fi
