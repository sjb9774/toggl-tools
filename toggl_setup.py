#! /usr/bin/env python

from argparse import ArgumentParser
import requests
import sh
from toggl import get_current_timer, get_branch_name, set_config, clear_config
from toggl import get_api_token

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
    p.add_argument("entry_name", help="The name of the  entry to toggl under by default for this branch.", nargs='?')
    p.add_argument("--billable", help="Pass this flag if you are working on a billable project.", action="store_true")
    p.add_argument("--task", help="The name of the task (if any).", action="store")
    p.add_argument("--project", help="Project tag (Education, Support, Funded, etc)", action="store")
    p.add_argument("--set-token", help="Allows you to set your api token again.", action="store_true")
    p.add_argument("--tags", help="Any additional tags that should be associated by default.", nargs='+', required=False)
    p.add_argument("--current-timer", help="Configures your setup match that of the currently running timer in toggl.", action='store_true')
    
    args = p.parse_args()
    
    # we're gonna use git configs by branch-name to keep track of all of this
        
    if not args.entry_name and not args.current_timer:
        print "Must supply either an 'entry_name' or pass the '--current-timer' flag."
        import sys; sys.exit(1)
    
    if is_first_time() or args.set_token:
        token = None
        while not token:
            token = raw_input("Please enter your API Token:\n")
            if token:
                sh.git('config', '--add', 'toggl.api-token', token)
                print "Token set to '{token}' successfully!".format(token=token)
            else:
                print "No token given, try again."
    
    if args.current_timer:
        current = get_current_timer()
        if current['data']:
            clear_config()
            print "Configuring from '{timer}' timer.".format(timer=current['data']['description'])
            data = current['data']
            set_config('entry', data.get('description', ''))
            for tag in data.get('tags', []):
                set_config('tags', tag)
            pid = data.get('pid')
            if pid:
                set_config('pid', pid)
            set_config('billable', data.get('billable', False))
            tid = data.get('tid')
            if tid:
                set_config('tid', tid)
            wid = data.get('wid')
            if wid:
                set_config('wid', wid)
        else:
            print "No timer currently running."
    else:
        clear_config()
        set_config('entry', args.entry_name)
        if args.billable:
            set_config('billable', 'true')
        if args.task:
            set_config('task', args.task)
        if args.project:
            set_config('project', args.project)
        if args.tags:
            for tag in args.tags:
                set_config('tags', tag)
    print "You're configured! Start a timer by running toggl start, stop with toggl stop."
