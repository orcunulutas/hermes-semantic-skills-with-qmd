#!/bin/bash
if [ "$1" = "--version" ]; then
    echo "qmd mock version"
elif [[ "$*" == *"collection list"* ]]; then
    echo "test-hermes-skills"
elif [[ "$*" == *"query"* && "$*" == *"--format json"* ]]; then
    echo '[{"file": "qmd://test-hermes-skills/exchange123/references/mailbox.md?index=test-hermes-skills", "score": 0.95}]'
fi
