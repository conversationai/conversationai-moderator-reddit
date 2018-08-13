# Perspective Moderation Bot

## Description

This repository contains a python script for a Reddit bot which uses the
Perspective API to help moderate comments on a subreddit. By specifying rules
in the `rules.yaml` file, the bot will check new comments on a given subreddit
for triggering these rules and can report those that do. In order for the
actions to be applied, the reddit credentials provided to the bot must have
moderation permissions on the subreddit being moderated.

## Setup

1. Setup a [virtualenv](https://virtualenvwrapper.readthedocs.io/en/latest/) for
   the project (recommended, but technically optional).

   Python 2:

   ```shell
   python -m virtualenv .venv
   ```

   To enter your virtual env:

   ```shell
   source env/bin/activate
   ```

2. Install library dependencies:

   ```shell
   pip install -r requirements.txt
   ```

3. Set up a `creds.py` file with your Reddit and Perspective API credentials.
   This file can be created by copying creds_template.py and filling in the
   appropriate fields in the dictionary. You can find more information about
   obtaining Reddit credentials from the [PRAW documentation](https://praw.readthedocs.io/en/latest/getting_started/authentication.html#script-application)
   and Perspective API credentials from
   [http://perspectiveapi.com/](http://perspectiveapi.com/).

4. Modify the moderation rules in `rules.yaml` as appropriate for your
   moderation task. The file contains comments with instructions on the syntax
   for these rules and examples of rules that can be adapted.

## Running the moderation bot

Once the setup is complete the bot can be run with the command:

```shell
python moderate_subreddit.py $SUBREDDIT_NAME
```

where you can replace $SUBREDDIT_NAME with the name of the subreddit you wish
to help moderate.

You can optionally specify the `-output_dir` flag to record the scores of
comments seen by the bot in jsonlines format.