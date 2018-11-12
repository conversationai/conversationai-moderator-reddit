# Perspective Moderation Bot

## Description

This repository contains a python script for a Reddit bot which uses the
Perspective API to help moderate comments on a subreddit. By specifying rules
in the `rules.yaml` file, the bot will check new comments on a given subreddit
for triggering these rules and can report those that do.

In order for the actions to be applied, the reddit credentials provided to the
bot must have moderation permissions on the subreddit being moderated.
TODO(jetpack): I don't believe having mod permissions is strictly necessary -
test this.

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
   obtaining Reddit credentials from the [PRAW
   documentation](https://praw.readthedocs.io/en/latest/getting_started/authentication.html#script-application)
   and Perspective API credentials from
   [https://perspectiveapi.com/](https://perspectiveapi.com/) (the [quickstart
   guide](https://github.com/conversationai/perspectiveapi/blob/master/quickstart.md)
   gives steps you'll need to take).

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

where you can replace `$SUBREDDIT_NAME` with the name of the subreddit you wish
to help moderate.

You can optionally specify the `-output_dir` flag to record the scores of
comments seen by the bot in ndjson format. This is _required_ if you want to use
the `check_mod_actions` and `compute_bot_metrics` in order to see how accurate
the bot's actions are.


## Quantitative evaluation of bot actions

### Check moderation actions

Run the `check_mod_actions` tool in order to see whether reports made by the bot
were removed by mods.

```shell
python check_mod_actions.py \
  -input_path $MODERATE_SUBREDDIT_OUTPUT_FILE \
  -output_path $CHECK_MOD_ACTIONS_OUTPUT_FILE \
  -no_mod_creds \
  -stop_at_eof \
  -hours_to_wait 24
```

The `-input_path` argument is the file written by `moderate_subreddit.py`. This
file contains the comments scored and actions taken by the bot.

This tool checks the moderation actions of all comments and saves the data to
`-output_path`.

`-stop_at_eof` indicates that the tool should stop running once it reaches the
end of the input file. If this isn't given, the tool will continue to read new
data appended to the input.

`-hours_to_wait` indicates how long to wait after a comment was posted before
checking whether it was removed by a moderator.

### Computing metrics

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
python compute_bot_metrics.py $CHECK_MOD_ACTIONS_OUTPUT_FILE
```
