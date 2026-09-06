#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
open "$DIR/launch_cli_1_default.command"
sleep 1
if [ -f "$DIR/launch_cli_2_beata.command" ]; then
    open "$DIR/launch_cli_2_beata.command"
fi
