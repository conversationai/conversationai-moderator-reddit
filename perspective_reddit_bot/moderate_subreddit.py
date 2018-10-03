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

from creds import creds
import perspective_client

import config


# TODO(nthain): support automated language detection.
LANGUAGE = 'en'


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


def apply_action(action_name, comment, descriptions):
  all_reasons = ', '.join(descriptions)

  # Reddit API requires report reasons to be max 100 characters
  if len(all_reasons) > 100:
    all_reasons = all_reasons[:97] + '...'

  if action_name == 'report':
    print('Reporting: %s' % all_reasons)
    comment.report(all_reasons)
  elif action_name == 'noop':
    print('no-op: taking no action')
  else:
    raise ValueError('Action "%s" not yet implemented.' % self.action_name)


def timestamp_string(timestamp):
  return datetime.utcfromtimestamp(timestamp).strftime('%Y%m%d_%H%M%S')


def comment_url(comment):
  return 'https://reddit.com' + comment.permalink


def print_moderation_decision(i, comment, rule):
  print('----------')
  print('Comment #%s: ' % i)
  print(comment.body.encode('utf-8'))
  print('URL: ', comment_url(comment))
  print('Rule: %s' % rule)
  print('Action: %s' % rule.action_name)
  print('Subreddit: %s' % comment.subreddit)


def append_comment_data(output_path,
                        comment,
                        comment_for_scoring,
                        action_dict,
                        scores):
  with open(output_path, 'a') as f:
    record = {
      'comment_id': comment.id,
      'link_id': comment.link_id,  # id of the post
      'parent_id': comment.parent_id,
      'subreddit': str(comment.subreddit),
      'permalink': comment_url(comment),
      'orig_comment_text': comment.body,
      'author': comment.author.name,
      'created_utc': timestamp_string(comment.created_utc),
      'bot_scored_utc': datetime.utcnow().strftime('%Y%m%d_%H%M%S')}
    if comment.body != comment_for_scoring:
      record['scored_comment_text'] = comment_for_scoring
    record.update(action_dict)
    record.update(scores)
    json.dump(record, f)
    f.write('\n')


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


def check_rules(index, comment, rules, scores):
  action_dict = defaultdict(list)
  for rule in rules:
    if rule.check_model_rules(scores, comment):
      action_dict[rule.action_name].append(rule.rule_description)
      print_moderation_decision(index, comment, rule)
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

  current_file_time = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
  output_path = None
  if output_dir:
    file_suffix = '%s_%s.json' % (subreddit_name, current_file_time)
    output_path = os.path.join(output_dir, file_suffix)

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
      action_dict = check_rules(i, comment, rules, scores)

      # Apply actions from triggered rules
      if recent_mod_permissions and initial_mod_permissions:
        for action, rule_strings in action_dict.items():
          apply_action(action, comment, rule_strings)

      # Maybe write comment scores to file
      if output_path:
        append_comment_data(output_path,
                            comment,
                            comment_for_scoring,
                            action_dict,
                            scores)
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
