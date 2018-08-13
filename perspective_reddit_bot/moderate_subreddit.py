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
 
"""A reddit bot which uses the Perpsective API to help moderate subreddits.

Args:
      subreddit: (required) A positional argument for the name of the subreddit 
                 to moderate.
      -rule_config_file: (optional) The file which contains moderation rules. 
                         Defaults to 'rules.yaml'
      -output_dir: (optional) If set, scores for all streamed commments are 
                   written to a file in this directory.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
from datetime import datetime
import os
import time
import pandas as pd
import praw
from sets import Set
import yaml

from creds import creds
import perspective_client
from perspective_rule import Rule
import score_dataset

TEXT_COLUMN = 'comment_text'

LANGUAGE = 'en'
# TODO(nthain): support automated language detection.


def parse_rules(filepath):
  rules = []
  models = Set()
  with open(filepath) as f:
    raw_rules = yaml.load_all(f)
    for r in raw_rules:
      rules.append(Rule(r['perspective_score'],
                        r['action'],
                        r.get('report_reason')))
      models.update(r['perspective_score'].keys())
  assert len(rules) > 0, 'Rules file empty!'
  return rules, list(models)


def bot_is_mod(reddit, subreddit):
  try:
    mods = subreddit.moderator()
    return reddit.user.me() in mods
  except Exception:
    return False


def score_subreddit(creds_dict,
                    subreddit_name,
                    rules,
                    models,
                    output_path=None):
  """Score subreddit commments via Perspective API and apply moderation rules.

  Args:
    creds_dict: (dict) A dictionary of API credentials for Perspective and 
                Reddit.
    subreddit_name: (str) The name of the subreddit to stream.
    rules: (list) A list of rules to apply to each comment.
    models: (list) A list of models that the API must call to apply rules.
    output_path: (str, optional) If supplied, all comments and scores will be 
                 written to this path.
  """

  reddit = praw.Reddit(client_id=creds_dict['reddit_client_id'],
                       client_secret=creds_dict['reddit_client_secret'],
                       user_agent=creds_dict['reddit_user_agent'],
                       username=creds_dict['reddit_username'],
                       password=creds_dict['reddit_password'])
  subreddit = reddit.subreddit(subreddit_name)
  mod_permissions = bot_is_mod(reddit, subreddit)

  if mod_permissions:
    print('Bot is moderator of subreddit.')
    print('Moderation actions will be applied.')
  else:
    print('Bot is not moderator of subreddit.')
    print('Moderation actions will not be applied.')

  perspective = perspective_client.PerspectiveClient(creds_dict['perspective_api_key'])

  for i, comment in enumerate(subreddit.stream.comments()):
    try:
      if i%100 == 0 and i > 0:
        print(i)
      if len(comment.body) > 20000:
        print('Comment too long, skipping...')
        continue
      df = pd.DataFrame()
      df = df.append({TEXT_COLUMN: comment.body}, ignore_index=True)
      scored_df = score_dataset.score_dataframe(df,
                                                TEXT_COLUMN,
                                                models,
                                                perspective,
                                                language=LANGUAGE)
      if output_path:
        with open(output_path, 'a') as f:
          scored_df.to_json(f, orient='records', lines=True)
          f.write('\n')

      for rule in rules:
        if rule.check_model_rules(scored_df):
          print('----------')
          print('Comment #%s: ' % i)
          print(comment.body.encode('utf-8'))
          print('Rule: %s' % rule)
          print('Action: %s' % rule.action_name)
          if subreddit_name in ['all', 'popular']:
            print('Subreddit: %s' % comment.subreddit)

          if mod_permissions:
            rule.apply_action(comment)
            print('ACTION APPLIED')
          else:
            print('ACTION NOT APPLIED')

          print('----------')
    except Exception as e:
      print('Skipping comment due to exception: %s' % e)


def _main():
  parser = argparse.ArgumentParser('A bot to moderate a subreddit \
                                    with the Perspective API.')
  parser.add_argument('subreddit', help='Subreddit to score')
  parser.add_argument('-rule_config_file', help='Models to request',
                      default='rules.yaml')
  parser.add_argument('-output_dir', help='Directory to save output scores',
                      default=None)

  args = parser.parse_args()
  if args.output_dir:
    file_suffix = '%s_%s.json' % (args.subreddit, 
                                  datetime.now().strftime('%Y%m%d_%H%M%S'))
    output_path = os.path.join(args.output_dir, file_suffix)
                               
  else:
    output_path = None
  rules, models = parse_rules(args.rule_config_file)
  score_subreddit(creds, args.subreddit, rules, models, output_path)

if __name__ == '__main__':
  _main()
