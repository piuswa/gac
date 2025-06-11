#!/bin/bash

echo "$SSH_ORIGINAL_COMMAND" >> 

pullpatt="git-upload-pack ''$"

pushpatt="git-receive-pack ''$"

cmd="$SSH_ORIGINAL_COMMAND"

if [[ $cmd =~ ^$pullpatt || $cmd =~ ^$pushpatt ]]; then
	exec git-shell -c "$SSH_ORIGINAL_COMMAND"
	exit
else
	echo "ACCESS DENIED"
	exit 1
fi
