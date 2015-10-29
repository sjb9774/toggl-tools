# toggl-tools
Toggl API command-line tools already exist, but to my knowledge this is the first that leverages
the power of `git`* to allow you to much more easily track time you spend programming.



## Requirements
This project uses the following libraries:
* [requests](http://docs.python-requests.org/en/latest/)
* [sh](https://amoffat.github.io/sh/)

## Getting started

First, clone this repo wherever you like on your machine. Then, create aliases `toggl` and
`toggl-setup` that refer to your particular installation locations.

After cloning, the first thing you'll want to do is go to your Toggl profile and get your 
API token. You'll be prompted for it when you first run `toggl-setup` (you can also reset 
it at any time by running `toggl-setup --set-token`).

I believe the easiest way to get started is to go to the toggl website each time you start
a new branch, create the appropriate timer you desire for the branch and start it. Then,
simply return to your local git repo and run `toggl-setup "my config" --current-timer`. It will save
the configuration of the timer currently running, then you can stop the timer with `toggl stop` 
and start it back up again with `toggl start "my config"`. You can even create hooks that run the commands
automatically when you switch between branches*.

If you don't want to have to touch the toggl website again, just run `toggl-setup --help`
and review the help options for how to manually configure a timer from the command line. An 
example command might look like 
`toggl-setup "big project" --entry-name "My Big Project" --project "Hackathon" --tags "important" "python" --billable`

## MVP
Right now toggl-tools works but has some (a lot) of rough edges. In order to create a what 
I would consider a minimum viable product, these things need to be changed/implemented:

- [ ] Caching responses needs to be much smarter.
- [X] A user should be able to pass their own configuration file.
  - [ ] A user should be able to set this as the default as well.
- [ ] `toggl-setup` should be re-implemented as a subcommand of `toggl`
- [X] The project should be refactored as needed to allow common actions to be placed in functions 
and this tool should simply be a pleasant means of interfacing with them.
- [ ] Exceptions need to be handled gracefully.
  - [ ] Failed requests need to return useful messages to the user.
- [ ] There must be adequate test coverage.
- [ ] README needs to be up-to-date with all the above changes.

Once these MVP goals are met, luxury functionality can begin to be planned.

*(The current master release doesn't actually leverage `git` at all anymore! That will be
reimplemented in a later release.)