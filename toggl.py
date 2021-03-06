#! /usr/bin/env python

from argparse import ArgumentParser
import requests
import sh
import json
from requests.auth import HTTPBasicAuth
import time
from ConfigParser import ConfigParser
requests.packages.urllib3.disable_warnings()

KEYWORDS = ("previous", "current", "this", "global", "paused")

def config_path():
    import os
    return os.path.expanduser('~/.toggl/toggl.cfg')
    
def config():
    cfg = ConfigParser()
    cfg.read(config_path())
    return cfg
    
def write_out(cfg):
    cfg.write(open(config_path(), 'w+'))
    
def get_branch_name():
    return sh.git('rev-parse', '--abbrev-ref', 'HEAD').strip('\n').replace('_', '-')
    
def set_config(section, key, value, _list=False):
    cfg = config()
    if not cfg.has_section(section):
        cfg.add_section(section)
    if _list:
        cfg.set(section, key, '::'.join(value))
    else:
        cfg.set(section, key, value)
    write_out(cfg)

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

def get_config(section, key, get_all=False, _list=False):
    cfg = config()
    if cfg.has_option(section, key):
        if _list:
            return cfg.get(section, key).split('::')
        else:
            return cfg.get(section, key)
    else:
        return None

def get_api_token():
    return config().get('global', 'api_token')

def get_section_from_name(name):
    cfg = config()
    for section in cfg.sections():
        if cfg.has_option(section, 'entry_name') and cfg.get(section, 'entry_name', name) == name:
            return section
    
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
    data = read_data()
    if data.get('workspaces'):
        return data.get('workspaces')
    else:
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
    
def clear_config(section=None):
    cfg = config()
    if section:
        cfg.remove_section(section)
    else:
        for section in cfg.sections():
            cfg.remove_section(section)
    write_out(cfg)
    
def delete_timer(timer_id):
    url = "https://www.toggl.com/api/v8/time_entries/{time_entry_id}".format(time_entry_id=timer_id)
    r = requests.delete(url, auth=(get_api_token(), 'api_token'))
    return r.json()

def get_duration_string(seconds):
    mins, sec = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    return "{hrs} hours, {mins} minutes, {secs} seconds".format(hrs=int(hrs), mins=int(mins), secs=int(sec))

def stop_timer(timer_id):
    url = "https://www.toggl.com/api/v8/time_entries/{time_entry_id}/stop".format(time_entry_id=timer_id)
    r = requests.put(url, auth=(get_api_token(), 'api_token'))
    return r.json()
    
def fetch_current(section="current"):
    """Gets the currently running timer and stores it in the config in the given
    section"""
    current = get_current_timer()
    if current.get('data'):
        clear_config(section=section)
        for key, value in current.get('data').iteritems():
            _list = type(value) == list
            if key == "duration":
                import time
                value += time.time()
                value = get_duration_string(value)
            set_config(section, key, value, _list=_list)
        return True
    return False
    
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
        
        payload['time_entry']['billable'] = bool(billable)
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
                    
def start_command(delete=False, **kwargs):
    set_config('paused', 'fresh', 'no')
    section = kwargs.get('name')
    for keyword in ('current', 'previous', 'this'):
        if kwargs.get(keyword):
            if keyword == "current":
                config_section = "current"
            elif keyword == "previous":
                config_section = get_config('global', 'previous') if config().has_option('global', 'previous') else None
            elif keyword == "this":
                config_section = get_branch_name()
            break
    else:
        config_section = kwargs.get('name')
    if not config_section:
        if kwargs.get('previous'):
            print "No previous timer found! Start a timer first."
        else:
            print "Must provide a configuration to use."
        import sys; sys.exit(1)
    
    # set up the "previous" timer in the config
    set_config('global', 'previous', config_section)
    
    if delete:
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
    entry = get_config(config_section, "entry")
    p_id = get_config(config_section, 'pid')
    if not p_id:
        project_name = get_config(config_section, 'project')
        if project_name:
            p_id = get_project_by_name(project_name)['id']
        
    tags = get_config(config_section, 'tags', _list=True)
        
    t_id = get_config(config_section, 'tid')
    if not t_id:
        task = get_config(config_section, 'task')
        if task:
            task_id = get_task_by_name(project_name, task)['id']
    w_id = get_config(config_section, 'wid')
    # gotta have at least one of these or the request will fail,
    # get the workspace as a last resort to avoid the extra request
    if not w_id and not t_id and not p_id:
        w_id = get_workspaces()[0]['data']['id']  
          
    billable = get_config(config_section, 'billable')
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
        
def stop_command(*args, **kwargs):
    set_config('paused', 'fresh', 'no')
    current_timer = get_current_timer()
    if current_timer['data']:
        data = stop_timer(current_timer['data']['id'])['data']
        if data:
            print "Successfully stopped '{timer_name}' timer.".format(timer_name=data.get('description', ''))
            duration = data.get('duration', 0)
            dur_str = get_duration_string(duration)
            print "Duration: {duration}".format(duration=dur_str)
            if kwargs.get('delete'):
                delete_timer(current_timer['data']['id'])
                print "Deleted timer '{timer}'.".format(timer=data.get('description', ''))
        else:
            print "Couldn't stop the running timer! v(o_o)v"
            
    else:
        print "No timer currently running."
        
def describe_command(*args, **kwargs):
    config_section = kwargs.get('name')
    if kwargs.get('previous'):
        config_section = get_config('global', 'previous')
    elif kwargs.get('current'):
        if fetch_current():
            config_section = "current"
        else:
            print "No timer currently running."
            import sys; sys.exit(0)
    elif kwargs.get('this'):
        config_section = get_branch_name()
    elif not config_section:
        print "Must provide a timer reference."

    if config_section and config().has_section(config_section):
        describe(config_section)
    elif config_section:
        print "No timer configuration under '{ref}'.".format(ref=config_section)

def describe(section):
    items = [("section", section)]
    other_items = config().items(section)
    for option, value in items + other_items:
        print "{opt}: {val}".format(opt=option.capitalize(), val=value.replace('::', ', '))
        
def pause_command(*args, **kwargs):
    if not fetch_current(section="paused"):
        print "No timer currently running, can't pause."
    else:
        current_timer_id = get_config("paused", "id")
        set_config("paused", "fresh", "yes")
        resp = stop_timer(current_timer_id)
        if not resp.get('data'):
            print "Couldn't stop the current timer for some reason. v(o_o)v"
        else:
            print "Paused '{name}' at {dur}. Resume this timer with toggl resume.".format(name=resp['data']['description'], 
                                                                                         dur=get_duration_string(resp['data']['duration']))

def resume_command(*args, **kwargs):
    if get_config('paused', 'fresh') == "yes":
        name = get_config('paused', 'description')
        task_id = get_config('paused', 'tid')
        workspace_id = get_config('paused', 'wid')
        tags = get_config('paused', 'tags', _list=True)
        project_id = get_config('paused', 'pid')
        billable = get_config('paused', 'billable') or False
        resp = start_timer(name=name,
                           task_id=task_id,
                           workspace_id=workspace_id,
                           tags=tags,
                           project_id=project_id,
                           billable=billable)
        if resp.get('data'):
            print "Resumed timer '{name}'.".format(name=get_config('paused', 'description'))
    else:
        print "No currently paused timer."
        
def list_command(*args, **kwargs):
    cfg = config()
    for section in cfg.sections():
        if section not in KEYWORDS:
            print section
            if kwargs.get('verbose'):
                print '------------------'
                describe(section)
                print '\n\n'
    
    
def do_argparse():
    p = ArgumentParser(description="Starts or stops your toggl timer.")
    p_subs = p.add_subparsers()
    start_parser = p_subs.add_parser("start", help="Start a timer based on your current configuration.")
    start_parser.set_defaults(func=start_command)
    
    stop_parser = p_subs.add_parser("stop", help="Stop the current timer.")
    stop_parser.set_defaults(func=stop_command)
    stop_parser.add_argument("--delete", action="store_true", help="Stops and deletes the current entry.")
    
    describe_parser = p_subs.add_parser("describe", help="Outputs the configuration for the given timer.")
    describe_parser.add_argument('name', nargs='?', action="store", help="The name under which the desired configuration was saved.")
    describe_parser.set_defaults(func=describe_command)
    
    start_parser.add_argument("name", metavar='config', action="store", help="If provided, the name of the entry configuration to start a timer with. Otherwise, looks for default settings.", nargs="?")
    start_parser.add_argument("--delete", action="store_true", help="Deletes the current entry and starts a new one with the current config.")
    
    pause_parser = p_subs.add_parser("pause", help="Pause the currently running timer such that you can start it again with 'resume'.")
    pause_parser.set_defaults(func=pause_command)
    
    resume_parser = p_subs.add_parser("resume", help="Resume a paused timer.")
    resume_parser.set_defaults(func=resume_command)
    
    list_parser = p_subs.add_parser("list", help="Outputs all the available configuration keys.")
    list_parser.add_argument("-v", "--verbose", action="store_true", help="Describes each entry in detail.")
    list_parser.set_defaults(func=list_command)
    
    args = p.parse_args()
    
    nice_args = list(args._get_args())
    nice_kwargs = dict(args._get_kwargs())
    for keyword in KEYWORDS:
        nice_kwargs[keyword] = nice_kwargs.get('name') == keyword
    return nice_args, nice_kwargs
    
if __name__ == "__main__":
    args, kwargs = do_argparse()
    kwargs.get('func')(*args, **kwargs)