# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A reddit bot which uses the Perpsective API to help moderate subreddits."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
from collections import defaultdict
from datetime import datetime
import os
import json
import praw

import config
from creds import creds
import perspective_client
from perspective_rule import REPORT_ACTION, NOOP_ACTION
from log_subreddit_comments import (
    append_record, comment_url, create_comment_output_record, now_timestamp
)


# TODO(nthain): support automated language detection.
LANGUAGE = 'en'

MODEL_SCORE_OUTPUT_PREFIX = 'score:'
RULE_OUTCOME_OUTPUT_PREFIX = 'rule:'
UNTRIGGERED_RULE_OUTPUT_VALUE = 'rule-not-triggered'

FILENAME_OUTPUT_PREFIX = 'modsubreddit_comments'


def remove_quotes(text):
  """Removes lines that begin with '>', indicating a Reddit quote."""
  lines = text.split('\n')
  nonquote_lines = [l for l in lines if not l.startswith('>')]
  text_with_no_quotes = '\n'.join(nonquote_lines).strip()
  return text_with_no_quotes or text


def bot_is_mod(reddit, subreddit):
  try:
    mods = subreddit.moderator()
    return reddit.user.me() in mods
  except Exception:
    return False


def apply_action(action_name, comment, rules):
  all_reasons = ', '.join(r.rule_description for r in rules)
  # Reddit API requires report reasons to be max 100 characters
  if len(all_reasons) > 100:
    all_reasons = all_reasons[:97] + '...'

  if action_name == REPORT_ACTION:
    print('Reporting: %s' % all_reasons)
    comment.report(all_reasons)
  elif action_name == NOOP_ACTION:
    print('no-op: taking no action')
  else:
    raise ValueError('Action "%s" not yet implemented.' % self.action_name)


def print_actions(i, comment, action_dict):
  print('----------')
  print('Comment #%s: ' % i)
  print(comment.body.encode('utf-8'))
  print('URL: ', comment_url(comment))
  print('Subreddit: %s' % comment.subreddit)
  print('Actions:')
  for action, rules in action_dict.iteritems():
    for rule in rules:
      print('  %s: %s: %s' % (action, rule.name, rule.rule_description))


def create_rule_outcomes_map(action_dict, all_rules):
  """Build map from each rule's name to which action was triggered, if any."""
  rule_outcomes = {}
  # action_dict contains the rules that were triggered.
  for action, rules in action_dict.iteritems():
    for rule in rules:
      rule_outcomes[rule.name] = action
  # Add all untriggered rules.
  for rule in all_rules:
    if rule.name not in rule_outcomes:
      rule_outcomes[rule.name] = UNTRIGGERED_RULE_OUTPUT_VALUE
  return rule_outcomes


def create_mod_comment_output_record(
    comment, comment_for_scoring, scores, action_dict, all_rules):
  record = create_comment_output_record(comment)

  if comment.body != comment_for_scoring:
    record['scored_comment_text'] = comment_for_scoring
  rule_outcomes = create_rule_outcomes_map(action_dict, all_rules)
  record.update({RULE_OUTCOME_OUTPUT_PREFIX + rule: outcome
                 for rule, outcome in rule_outcomes.iteritems()})
  record.update({MODEL_SCORE_OUTPUT_PREFIX + model: score
                 for model, score in scores.iteritems()})
  return record


def score_comment(comment,
                  perspective,
                  api_models,
                  ensembles,
                  should_remove_quotes):
  initial_comment = comment.body
  comment_for_scoring = (remove_quotes(initial_comment)
                          if should_remove_quotes else initial_comment)
  if len(comment_for_scoring) > 20000:
    print('Comment too long, skipping...')
    return None, None
  scores = perspective.score_text(comment_for_scoring, api_models,
                                  language=LANGUAGE)
  for e in ensembles:
    scores[e.name] = e.predict_one(scores)

  return comment_for_scoring, scores


def check_rules(comment, rules, scores):
  """Returns mapping from actions to triggered rules."""
  action_dict = defaultdict(list)
  for rule in rules:
    if rule.check_model_rules(scores, comment):
      action_dict[rule.action_name].append(rule)
  return action_dict


def score_subreddit(creds_dict,
                    subreddit_name,
                    rules,
                    api_models,
                    ensembles,
                    should_remove_quotes,
                    output_dir=None):
  """Score subreddit commments via Perspective API and apply moderation rules.

  Args:
    creds_dict: (dict) A dictionary of API credentials for Perspective and
                Reddit.
    subreddit_name: (str) The name of the subreddit to stream.
    rules: (list) A list of rules to apply to each comment.
    api_models: (list) A list of models that the API must call to apply rules.
    ensembles: (list) A list of ensemble models based on the API models to
      additionally score each comment with.
    should_remove_quotes: (bool) Whether to remove Reddit quotes before scoring.
    output_dir: (str, optional) If supplied, all comments and scores will be
                 written to this directory.
  """

  reddit = praw.Reddit(client_id=creds_dict['reddit_client_id'],
                       client_secret=creds_dict['reddit_client_secret'],
                       user_agent=creds_dict['reddit_user_agent'],
                       username=creds_dict['reddit_username'],
                       password=creds_dict['reddit_password'])
  subreddit = reddit.subreddit(subreddit_name)
  initial_mod_permissions = bot_is_mod(reddit, subreddit)
  recent_mod_permissions = initial_mod_permissions

  if initial_mod_permissions:
    print('Bot is moderator of subreddit.')
    print('Moderation actions will be applied.')
  else:
    print('Bot is not moderator of subreddit.')
    print('Moderation actions will not be applied.')

  perspective = perspective_client.PerspectiveClient(
    creds_dict['perspective_api_key'])

  output_path = None
  if output_dir:
    output_path = os.path.join(
        output_dir,
        '{}_{}_{}.json'.format(FILENAME_OUTPUT_PREFIX, subreddit_name,
                               now_timestamp()))

  for i, comment in enumerate(subreddit.stream.comments()):
    try:
      if i % 100 == 0 and i > 0:
        print(i)
        # Check if still has mod permissions every 100 comments
        recent_mod_permissions = bot_is_mod(reddit, subreddit)

      # Score current comment with perspective models
      comment_for_scoring, scores = score_comment(comment,
                                                  perspective,
                                                  api_models,
                                                  ensembles,
                                                  should_remove_quotes)
      if scores is None:
        continue

      # Check which rules should be applied
      action_dict = check_rules(comment, rules, scores)
      if action_dict:
        print_actions(i, comment, action_dict)

      # Apply actions from triggered rules
      if recent_mod_permissions and initial_mod_permissions:
        for action, triggered_rules in action_dict.iteritems():
          apply_action(action, comment, triggered_rules)

      # Maybe write comment scores to file
      if output_path:
        output_record = create_mod_comment_output_record(
            comment, comment_for_scoring, scores, action_dict, rules)
        append_record(output_path, output_record)
    except Exception as e:
      print('Skipping comment due to exception: %s' % e)


def _main():
  parser = argparse.ArgumentParser(
      'A bot to moderate a subreddit with the Perspective API.')
  parser.add_argument('subreddit', help='subreddit to moderate')
  parser.add_argument('-config_file', help='config file with moderation rules',
                      default='config.yaml')
  parser.add_argument('-remove_quotes', help='remove quotes when scoring text',
                      default=True)
  parser.add_argument('-output_dir',
                      help='if set, comment scores are saved to this directory',
                      default=None)

  args = parser.parse_args()

  rules, api_models, ensembles = config.parse_config(args.config_file)
  score_subreddit(creds, args.subreddit, rules, api_models, ensembles,
                  args.remove_quotes, args.output_dir)


if __name__ == '__main__':
  _main()
