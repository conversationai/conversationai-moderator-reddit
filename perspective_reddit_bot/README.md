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
   source .venv/bin/activate
   ```

2. Install library dependencies:

   ```shell
   pip install -r requirements.txt
   ```

3. Set up a `creds.json` file with your Reddit and Perspective API credentials.
   This file can be created by copying `creds_template.json` and filling in the
   appropriate fields in the dictionary. You can find more information about
   obtaining Reddit credentials from the [PRAW documentation](https://praw.readthedocs.io/en/latest/getting_started/authentication.html#script-application)
   and Perspective API credentials from
   [http://perspectiveapi.com/](http://perspectiveapi.com/).

4. Modify the moderation rules in `rules.yaml` as appropriate for your
   moderation task. The file contains comments with instructions on the syntax
   for these rules and examples of rules that can be adapted.

## Running tests

TODO: use a standard test runner thing?

```shell
source .venv/bin/activate
python -m unittest discover -s . -p '*_test.py'
```

## Running the moderation bot

Once the setup is complete the bot can be run with the command:

```shell
python moderate_subreddit.py $SUBREDDIT_NAME
```

where you can replace $SUBREDDIT_NAME with the name of the subreddit you wish
to help moderate.

You can optionally specify the `-output_dir` flag to record the scores of
comments seen by the bot in jsonlines format.

## Quantitative evaluation of bot actions

TODO: add some notes on running `check_mod_actions`.

The output of `check_mod_actions` can be evaluated to see how well the bot is
performing. Namely: how well is the bot flagging comments that should be
removed?

The `compute_bot_metrics` tool computes precision and recall metrics for each of
the bot rules, as well as the bot's actions overall. The tool assumes that
removed comments were removed due to moderation. For each rule, the tool
computes:

- precision: how many flagged comments were removed
- recall: how many removed comments were flagged by the bot due to the rule

As we do not have rule-level data, these definitions don't correspond exactly to
standard precision and recall metrics. In particular, precision may be
artificially high (as the rule can get credit for a comment that was actually
removed for another reason) and recall may be artificially low (as the rule may
be penalized for comments that it was not supposed to capture). However, both
metrics still provide some evidence as to the effectiveness of the rule.



```shell
python compute_bot_metrics.py $check_mod_actions_output_file
```
