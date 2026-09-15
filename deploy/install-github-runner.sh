#!/bin/bash
# Prepares the Linux machine for a GitHub self-hosted runner

RUNNER_USER="github-runner"
if ! id "$RUNNER_USER" &>/dev/null; then
  useradd -m -s /bin/bash "$RUNNER_USER"
fi

cd /home/$RUNNER_USER
if [ ! -d "actions-runner" ]; then
  mkdir actions-runner && cd actions-runner
  curl -o actions-runner-linux-x64-2.314.1.tar.gz -L https://github.com/actions/runner/releases/download/v2.314.1/actions-runner-linux-x64-2.314.1.tar.gz
  tar xzf ./actions-runner-linux-x64-2.314.1.tar.gz
  chown -R $RUNNER_USER:$RUNNER_USER .
  echo "GitHub actions runner downloaded. Run ./config.sh as $RUNNER_USER when registration token is authorized."
fi
