#! /usr/bin/env python

from argparse import ArgumentParser
import requests
import sh
import json
from requests.auth import HTTPBasicAuth
import time

def get_branch_name():
    return sh.git('rev-parse', '--abbrev-ref', 'HEAD').strip('\n').replace('_', '-')

def set_config(key, value):
    branch_name = get_branch_name()
    command = ['config', '--add', '{branch}.{key}'.format(branch=branch_name, key=key), value]
    sh.git(*command)

def write_data(section, write_this):
    current_data = read_data()
    with open('/tmp/toggl.json', 'w+') as f:
        data = current_data
        data.setdefault(section, {})
        data[section] = write_this
        f.write(json.dumps(data))

def read_data():
    import os
    if os.path.exists('/tmp/toggl.json'):
        with open('/tmp/toggl.json', 'r') as f:
            content = f.read()
            if content:
                return json.loads(content)
            else:
                return {}
    else:
        return {}

def get_config(key, get_all=False, dtype=''):
    branch_name = get_branch_name()
    command = ['config', '--get{all}'.format(all="-all" if get_all else ''), '{branch}.{key}'.format(branch=branch_name.replace('_', '-'), key=key)]
    if dtype:
        command.append('--{dtype}'.format(dtype=dtype))
    try:
        return sh.git(*command).strip('\n')
    except:
        return None

def get_api_token():
    branch_name = get_branch_name()
    command = ['config', '--get', 'toggl.api-token']
    return sh.git(*command).strip('\n')
    
def get_projects(workspace):
    w_id = workspace['id']
    url = "https://www.toggl.com/api/v8/workspaces/{workspace_id}/projects".format(workspace_id=w_id)
    r = requests.get(url, auth=(get_api_token(), 'api_token'))
    # automatically cache this stuff and it will save us a lot requests in the future
    write_data('projects', r.json())
    return r.json()
    
def get_project_by_name(name):
    data = read_data()
    projects = data.get('projects', [])
    project = None
    for p in projects:
        if p['name'] == name:
            project = p
    if project:
        return project
    else:
        # assume only one possible workspace by default
        projects = get_projects(get_workspaces()[0])
        return [project for project in projects if project['name'] == name][0]

def get_project_by(_refresh=True, **kwargs):
    data = read_data()
    projects = data.get('projects', [])
    if projects:
        matching_projects = []
        for project in projects:
            for kw in kwargs:
                if project.get(kw) and project[kw] == kwargs[kw]:
                    matching_projects.append(project)
        if matching_projects:
            return matching_projects[0]
    if _refresh:
        # the following call will refresh the cache and we'll call this function again
        # but don't refresh on that call
        projects = get_projects(get_workspaces()[0])
        get_project_by_id(_refresh=False, **kwargs)
    return None
        
def get_workspaces():
    url = "https://www.toggl.com/api/v8/workspaces"
    r = requests.get(url, auth=(get_api_token(), 'api_token'))
    return r.json()

def get_project_tasks(pid):
    url = "https://www.toggl.com/api/v8/projects/{project_id}/tasks".format(project_id=pid)
    r = requests.get(url, auth=(get_api_token(), 'api_token'))
    return r.json()

# all tasks belong to one project    
def get_task_by_name(project_name, task_name):
    project = get_project_by_name(project_name)
    tasks = get_project_tasks(project['id'])
    return [t for t in tasks if t['name'] == task_name][0]
    
def get_current_timer():
    url = "https://www.toggl.com/api/v8/time_entries/current"
    r = requests.get(url, auth=(get_api_token(), 'api_token'))
    return r.json()

def get_timer_info(timer_id):
    url = "https://www.toggl.com/api/v8/time_entries/{time_entry_id}".format(time_entry_id=timer_id)
    r = requests.get(url, auth=(get_api_token(), 'api_token'))
    return r.json()
    
def clear_config():
    try:
        sh.git('config', '--remove-section', get_branch_name())
    except:
        pass
    
def delete_timer(timer_id):
    url = "https://www.toggl.com/api/v8/time_entries/{time_entry_id}".format(time_entry_id=timer_id)
    r = requests.delete(url, auth=(get_api_token(), 'api_token'))
    return r.json()

def get_duration_string(seconds):
    mins, sec = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    return "{hrs} hours, {mins} minutes, {secs} seconds.".format(hrs=hrs, mins=mins, secs=sec)

def stop_timer(timer_id):
    url = "https://www.toggl.com/api/v8/time_entries/{time_entry_id}/stop".format(time_entry_id=timer_id)
    r = requests.put(url, auth=(token, 'api_token'))
    return r.json()
    
def start_timer(name="", 
                tags=None, 
                task_id=None, 
                project_id=None, 
                workspace_id=None, 
                billable=False,
                auth=None):
    if not workspace_id and not project_id and not task_id:
        raise ValueError("One of 'workspace_id', 'project_id', or 'task_id' must be supplied.")
    else:
        if not auth:
            auth = (get_api_token(), 'api_token')
        payload = {
            "time_entry": {
                "description": name,
                "created_with": "toggl tool"
            }
        }
        
        payload['time_entry']['billable'] = billable
        if tags:
            payload['time_entry']['tags'] = tags
        if project_id:
            payload['time_entry']['pid'] = project_id
        if task_id:
            payload['time_entry']['tid'] = task_id
        if workspace_id:
            payload['time_entry']['wid'] = workspace_id
        
        url = "https://www.toggl.com/api/v8/time_entries/start"
        r = requests.post(url, json=payload, auth=auth)
        return r.json()
            
if __name__ == "__main__":
    p = ArgumentParser(description="Starts or stops your toggl timer.")
    p.add_argument("command", action="store", help="'start' or 'stop' to start or stop a timer, 'current-timer' for information about the timer currently active, if any.")
    p.add_argument("--name", action="store", help="Use a different entry name than what is set up in the config.")
    p.add_argument("--delete", action="store_true", help="Deletes the current entry if passed with 'start', or deletes the stopped entry.")
    
    args = p.parse_args()
    entry = args.name if args.name else get_config('entry')
    token = get_api_token()
    
    if args.command.lower() == "start":
        if args.delete:
            current = get_current_timer()
            if current['data']:
                stop_timer(current['data']['id'])
                print "Deleting current timer '{timer}'.".format(timer=current['data']['description'])
                resp = delete_timer(current['data']['id'])
                if resp:
                    deets = get_timer_info(resp[0])
                    print "Deleted timer '{timer}'.".format(timer=deets['data']['description'])
                    print "Total duration: {dur_str}".format(dur_str=get_duration_string(deets['data']['duration']))
            else:
                print "No timer currently running, can't delete. Starting new timer."
        # toggl_setup.py sets up the config with useful values as desired by the user,
        # here is where we fetch the information and use it for the entry description
        p_id = get_config('pid')
        if not p_id:
            project_name = get_config('project')
            if project_name:
                p_id = get_project_by_name(project_name)['id']
            
        tags = get_config('tags', get_all=True)
        if tags:
            tags = tags.split('\n')
            
        t_id = get_config('tid')
        if not t_id:
            task = get_config('task')
            if task:
                task_id = get_task_by_name(project_name, task)['id']
        w_id = get_config('wid')
        
        billable = get_config('billable')
        billable = billable and billable.lower() == "true"
        
        timer_response = start_timer(name=entry, 
                                     project_id=p_id, 
                                     task_id=t_id, 
                                     tags=tags, 
                                     workspace_id=w_id, 
                                     billable=billable)
        if timer_response['data']:
            print "Tracking '{entry}'.".format(entry=entry)
        else:
            print "Unknown problem starting the timer."
            
    elif args.command.lower() == "stop":
        current_timer = get_current_timer()
        
        if current_timer['data']:
            data = stop_timer(current_timer['data']['id'])['data']
            if data:
                print "Successfully stopped '{timer_name}' timer.".format(timer_name=data.get('description', ''))
                
                duration = data.get('duration', 0)
                dur_str = get_duration_string(duration)
                print "Duration: {duration}".format(duration=dur_str)
                if args.delete:
                    delete_timer(current_timer['data']['id'])
                    print "Deleted timer '{timer}'.".format(timer=data['description'])
                    
            else:
                print "Couldn't stop the running timer! v(o_o)v"
                
        else:
            print "No timer currently running."
    elif args.command.lower() == "current-timer":
        current_timer = get_current_timer()
        if current_timer['data']:
            print "Current timer is '{timer}'.".format(timer=current_timer['data']['description'])
            dur_str = get_duration_string(current_timer['data']['duration'] + int(time.time()))
            print "Current duration: {dur_str}".format(dur_str=dur_str)
            if current_timer['data']['tags']:
                print 'Tags: {tags}\t\t'.format(tags=', '.join(current_timer['data']['tags']))
            if current_timer['data']['pid']:
                print "Project: {project_name}".format(project_name=get_project_by(id=current_timer['data']['pid'])['name'])
            print "Billable: {billable}".format(billable=current_timer['data']['billable'])
        else:
            print "No timer currently running."
            
    else:
        print "{} is not 'start', 'current-timer', or 'stop'.".format(args.command)