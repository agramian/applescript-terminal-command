#!/usr/bin/python

import applescript_terminal_command
commands = [
    {'command': 'cd ~/Documents'},
    {'command': 'ls'},
    {'command': 'pwd',
     'delay': 5},
    {'command': 'asdf',
     'ignore_return_code': True},
    {'command': 'echo 1; sleep 5; echo \\"hello how are you\\"',
     'wait_for_output': ['you', 'are'],
     'wait_for_command': False}]
applescript_terminal_command.run_applescript_command(commands)
