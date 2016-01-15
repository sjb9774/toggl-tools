#! /usr/bin/env python

from argparse import ArgumentParser
import requests
import sh
import os
from toggl import get_current_timer, get_branch_name, set_config, clear_config
from toggl import get_api_token, get_section_from_name, config_path

def is_first_time():
    try:
        t = get_api_token()
        if t:
            return False
        else:
            return True
    except:
        return True

if __name__ == "__main__":
    p = ArgumentParser(description="Helps you configure some toggl shortcuts for your current branch.")
    p.add_argument("config_key", metavar='config-key', action="store", help="The configuration name to use for this setup. Later you will pass this same argument to `toggl start` to start this timer.")
    p.add_argument("--entry-name", action="store", help="The name of the  entry to toggl under by default for this branch. If not provided it will be the same as the config-key.")
    p.add_argument("--billable", help="Pass this flag if you are working on a billable project.", action="store_true")
    p.add_argument("--task", help="The name of the task (if any).", action="store")
    p.add_argument("--project", help="Project tag (Education, Support, Funded, etc)", action="store")
    p.add_argument("--set-token", help="Allows you to set your api token again.", action="store_true")
    p.add_argument("--tags", help="Any additional tags that should be associated by default.", nargs='+', required=False)
    p.add_argument("--current-timer", help="Configures your setup match that of the currently running timer in toggl.", action='store_true')
    p.add_argument("--clear", action="store_true", help="Clear the specified entry configuration before writing the new.")
    
    args = p.parse_args()
    if not os.path.exists(os.path.expanduser('~/.toggl')):
        os.mkdir(os.path.expanduser('~/.toggl'))
    if not os.path.exists(config_path()):
        open(config_path(), 'a').close()
    section = get_branch_name() if args.config_key == "this" else args.config_key
    name = args.entry_name if args.entry_name else section
    forbidden_names = ('previous', 'current', 'this')
    if name.lower() in forbidden_names:
        print "Name can't be any of {names}".format(names=', '.join(forbidden_names))
        import sys; sys.exit(1)
    
    if is_first_time() or args.set_token:
        token = None
        while not token:
            token = raw_input("Please enter your API Token:\n")
            if token:
                set_config('global', 'api_token', token)
                print "Token set to '{token}' successfully!".format(token=token)
            else:
                print "No token given, try again."
    
    if args.current_timer:
        current = get_current_timer()
        if current['data']:
            print "Configuring from '{timer}' timer.".format(timer=current['data'].get('description'))
            data = current['data']
            name = args.entry_name if args.entry_name else data.get('description')
            if args.clear and name:
                clear_config(section)
            elif args.clear:
                print "Not clearing config because entry name is empty or could not be found."
            set_config(section, 'entry', name)
            tags = data.get('tags', [])
            set_config(section, 'tags', tags, _list=True)
            pid = data.get('pid')
            if pid:
                set_config(section, 'pid', pid)
            set_config(section, 'billable', data.get('billable', False))
            tid = data.get('tid')
            if tid:
                set_config(section, 'tid', tid)
            wid = data.get('wid')
            if wid:
                set_config(section, 'wid', wid)
        else:
            print "No timer currently running."
    else:
        if args.clear:
            clear_config(section)
        set_config(section, 'entry', name)
        if args.billable:
            set_config(section, 'billable', 'true')
        if args.task:
            set_config(section, 'task', args.task)
        if args.project:
            set_config(section, 'project', args.project)
        if args.tags:
            set_config(section, 'tags', args.tags, _list=True)
            
    print "You're configured! Start a timer by running toggl start, stop with toggl stop."
