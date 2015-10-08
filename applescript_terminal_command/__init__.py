#!/usr/bin/python

import sys, os, traceback
import time
from shell import shell
import argparse
import subprocess
import signal
from subprocess_manager.run_subprocess import run_subprocess

class ShellCommandError(Exception): pass
class ShellCommandTimeoutError(Exception): pass

# source: http://stackoverflow.com/a/23646049
def reverse_readline(filename, buf_size=8192):
    """a generator that returns the lines of a file in reverse order"""
    with open(filename) as fh:
        segment = None
        offset = 0
        fh.seek(0, os.SEEK_END)
        total_size = remaining_size = fh.tell()
        while remaining_size > 0:
            offset = min(total_size, offset + buf_size)
            fh.seek(-offset, os.SEEK_END)
            buffer = fh.read(min(remaining_size, buf_size))
            remaining_size -= buf_size
            lines = buffer.split('\n')
            # the first line of the buffer is probably not a complete line so
            # we'll save it and append it to the last line of the next buffer
            # we read
            if segment is not None:
                # if the previous chunk starts right from the beginning of line
                # do not concact the segment to the last line of new chunk
                # instead, yield the segment first
                if buffer[-1] is not '\n':
                    lines[-1] += segment
                else:
                    yield segment
            segment = lines[0]
            for index in range(len(lines) - 1, 0, -1):
                if len(lines[index]):
                    yield lines[index]
        yield segment

# escape quotes
def escape_command(command):
    return command.replace("'", "\\'")

# remove previous out file
def remove_file(path):
    if os.path.exists(path):
        os.remove(path)
        while os.path.exists(path):
            time.sleep(0.1)
def wait_for_file(path):
     # wait for process to finish writing to file
    try:
        with open(path, 'a'):
            pass
    except IOError:
        print "File in use. Waiting..."
        time.sleep(0.1)
# out file path
script_dir = os.path.dirname(os.path.realpath(__file__))
out_file_path = os.path.join(script_dir, 'out.txt')
returncode_file_path = os.path.join(script_dir, 'returncode.txt')
def run_applescript_command(commands):
    # open a new window
    #window_name = time.strftime("window%Y%m%d%H%M%S")
    cmd = shell('osascript -e \'tell application "Terminal" to do script ""\'')
    window_ref =  cmd.output(raw=True).strip()
    # run each command
    print "Running command(s): %s" %('; '.join([c['command'] for c in commands]) + ';').replace(';; ', '; ')
    command_process_stdout = None
    command_process_stderr = None
    try:
        for c in commands:
            cmd_out_write_path = cmd_out_read_path = out_file_path
            if c.has_key('write_dir'):
                cmd_out_write_path = os.path.join(c['write_dir'], 'out.txt')
            if c.has_key('read_dir'):
                cmd_out_read_path = os.path.join(c['read_dir'], 'out.txt')
            rc_write_path = rc_read_path = returncode_file_path
            if c.has_key('write_dir'):
                rc_write_path = os.path.join(c['write_dir'], 'returncode.txt')
            if c.has_key('read_dir'):
                rc_read_path = os.path.join(c['read_dir'], 'returncode.txt')
            remove_file(cmd_out_read_path)
            remove_file(rc_read_path)
            num_exits = c['num_exits'] if c.has_key('num_exits') else 1
            command_str = ('osascript -e \'tell application "Terminal"\' '
                           '-e \'do script "%s%s" in %s\' '
                           '%s'
                           '%s'
                           '-e \'delay %s\' '
                           '-e \'end tell\''
                           %(escape_command(c['command']),
                            '' if (c.has_key('ignore_output') and c['ignore_output']) else ' &> %s'  %cmd_out_write_path,
                            window_ref,
                            '' if (c.has_key('dont_wait_for_command') and c['dont_wait_for_command']) else '-e \'repeat\' -e \'delay 0.1\' -e \'if not (get busy of %s) then exit repeat\' -e \'end repeat\' ' %window_ref,
                            '' if (c.has_key('ignore_return_code') and c['ignore_return_code']) else '-e \'do script "echo $? > %s" in %s\' ' %(rc_write_path,window_ref),
                            c['delay'] if c.has_key('delay') else 0))
            print c
            print command_str
            # run a subprocess to tail the out file so that output is shown in realtime to the console
            tail_process, command_starttime, command_process_stdout, command_process_stderr = run_subprocess('/bin/bash', ['-l', '-c', 'while [ ! -f {path} ]; do sleep 2; done; tail -f {path}'.format(path=cmd_out_read_path)], daemon=True, return_std=True)
            return_code = os.system(command_str)
            if not c.has_key('ignore_output') or not c['ignore_output']:
                wait_for_file(cmd_out_read_path)
                time.sleep(0.5)
                contains = []
                not_contains = []
                contains_any = []
                def append_to_text_list(item, text_list):
                    if type(item) == str:
                        text_list.append(item)
                    elif type(item) == list:
                        text_list += item
                # wait until certain output text is printed by the command
                if c.has_key('wait_for_output'):
                    text = c['wait_for_output']
                    if type(text) == dict:
                        if text.has_key('contains'):
                            append_to_text_list(text['contains'], contains)
                        if text.has_key('not_contains'):
                            append_to_text_list(text['not_contains'], not_contains)
                        if text.has_key('contains_any'):
                            append_to_text_list(text['contains_any'], contains_any)
                    else:
                        if type(text) == str:
                            contains = [text]
                        elif type(text) == list:
                            contains = text
                    if contains:
                        print "Waiting for command to output the following text string(s): %s" %contains
                    if contains_any:
                        print "Waiting for command to output ANY of the following text string(s): %s" %contains_any
                    start = time.time()
                    timeout = c['timeout'] if c.has_key('timeout') else 30
                    while True:
                        time_elapsed = time.time() - start
                        if time_elapsed > timeout:
                            raise ShellCommandTimeoutError('%s second(s) elapsed and the appropriate output string(s) were not found.' %(int(time_elapsed)))
                        with open(cmd_out_read_path) as f:
                            file_content = f.read()
                            if ((not contains or len([x for x in contains if x in file_content]) == len(contains))
                                and (not contains_any or len([x for x in contains_any if x in file_content]) >= 1)):
                                break
                # verify exclude strings are not present if necessary
                if not_contains:
                    with open(cmd_out_read_path) as f:
                        file_content = f.read()
                        print "Making sure output does NOT contain the following text string(s): %s" %not_contains
                        if len([x for x in not_contains if x in file_content]) > 0:
                            raise ShellCommandTimeoutError('One or more of the exclude strings was found in the command output.')
            last_line = ''
            for value in reverse_readline(cmd_out_read_path):
                last_line = value.strip() if value else ''
                if last_line.strip():
                    break
            if last_line.strip():
                last_line_printed = ''
                while last_line.strip() != last_line_printed.strip():
                    try:
                        last_line_printed = command_process_stdout.get_all_output().rstrip().splitlines()[-1]
                    except:
                        pass
                    time.sleep(2)
            # read and print returncode file
            if not c.has_key('ignore_return_code') or not c['ignore_return_code']:
                wait_for_file(rc_read_path)
                with open(rc_read_path) as f:
                    content = f.read().strip()
                    if not content:
                        continue
                    return_code = int(content)
                    if return_code != 0:
                        raise ShellCommandError('Return code: %s' %return_code)
            try:
                os.killpg(tail_process.pid, signal.SIGTERM)
            except:
                print(traceback.format_exc())
    except:
        print(traceback.format_exc())
        try:
            os.killpg(tail_process.pid, signal.SIGTERM)
        except:
            print(traceback.format_exc())
        return_code = 1
    finally:
        print "Closing Terminal window..."
        print "Running Exit command %s time(s)" %num_exits
        for i in range(0, num_exits):
            time.sleep(0.5)
            os.system('osascript -e \'tell application "Terminal" to do script "exit 0" in  %s\'' %window_ref)
        # quit terminal app if specified
        if c.has_key('quit_after') and c['quit_after']:
            os.system('osascript -e \'quit application "Terminal"')
        print 'return_code:', return_code
        print '\nSuccessfully ran command(s).' if return_code == 0 else 'FAILURE: One or more commands failed. Read output for details.'
        return(return_code)

if __name__ == "__main__":
    # i believe this check was to prevent from running on linux but not sure
    # commenting out since was preventing this from running through buildbot
    #if sys.stdin.isatty():
    # parse command line args
    parser = argparse.ArgumentParser(description='Execute a shell command using AppleScript')
    parser.add_argument('--commands',
                        dest='commands',
                        nargs='*',
                        help="String enclosed shell command(s) separated by spaces. Quotes within commands should be escaped. Ex: --commands 'echo 1' 'echo \\\"hello\\\"' 'echo 3'",
                        required=True)
    parser.add_argument('--delay',
                        dest='delay',
                        help="Number of seconds to wait before executing the next command.",
                        default=0)
    parser.add_argument('--quit_after',
                        dest='quit_after',
                        help="Whether to close the Terminal app once the commands have been run.",
                        default=False)
    args = parser.parse_args()
    commands = [{'command': c, 'delay': args.delay, 'quit_after': args.quit_after} for c in args.commands]
    sys.exit(run_applescript_command(commands))
