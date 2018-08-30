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
from datetime import datetime
import os
import json
import time
import praw
from sets import Set
import yaml

from creds import creds
import ensemble
import perspective_client
from perspective_rule import Rule

# TODO(nthain): support automated language detection.
LANGUAGE = 'en'

# TODO(jetpack): maybe move this to perspective_client?
AVAILABLE_API_MODELS = set([
    'TOXICITY',
    'SEVERE_TOXICITY',
    'IDENTITY_ATTACK',
    'INSULT',
    'PROFANITY',
    'THREAT',
    'SEXUALLY_EXPLICIT',
    'ATTACK_ON_AUTHOR',
    'ATTACK_ON_COMMENTER',
    'INCOHERENT',
    'INFLAMMATORY',
    'LIKELY_TO_REJECT',
    'OBSCENE',
    'SPAM',
    'UNSUBSTANTIAL',
])


def _has_duplicates(xs):
  return len(xs) != len(set(xs))


# TODO(jetpack): move this logic to config.py module.
def load_rules(rules_config):
  rules = []
  # Note: models mentioned in rules may contain the names of ensemble models.
  models = set()
  for r in rules_config:
    rules.append(Rule(r['perspective_score'],
                      r['action'],
                      r.get('report_reason')))
    models.update(r['perspective_score'].keys())
  assert len(rules) > 0, 'Rules file empty!'
  return rules, models


def remove_quotes(text):
  """Removes lines that begin with '>', indicating a Reddit quote."""
  lines = text.split('\n')
  nonquote_lines = [l for l in lines if not l.startswith('>')]
  text_with_no_quotes = '\n'.join(nonquote_lines).strip()
  return text_with_no_quotes or text


def load_ensembles(ensembles_config):
  ensembles = []
  api_models = set()
  for e in ensembles_config:
    ensembles.append(ensemble.LrEnsemble(e['name'], e['feature_weights'],
                                         e['intercept_weight']))
    api_models.update(e['feature_weights'].keys())

  ensemble_names = [e.name for e in ensembles]
  if _has_duplicates(ensemble_names):
    raise ValueError('Duplicate ensemble names! {}'.format(ensemble_names))
  ensembles_with_api_model_names = [e for e in ensemble_names
                                    if e in AVAILABLE_API_MODELS]
  if ensembles_with_api_model_names:
    raise ValueError(
        'Ensembles cannot have the same name as an API model: {}'.format(
            ensembles_with_api_model_names))

  return ensembles, api_models


def parse_config(filepath):
  with open(filepath) as f:
    config = yaml.load(f)

  ensembles, api_models_for_ensembles = [], set()
  if 'ensembles' in config:
    ensembles, api_models_for_ensembles = load_ensembles(config['ensembles'])

  rules, models_for_rules = load_rules(config['rules'])

  ensemble_names = set(e.name for e in ensembles)
  api_models_for_rules = [m for m in models_for_rules
                          if m not in ensemble_names]
  api_models = api_models_for_ensembles.union(api_models_for_rules)
  bad_api_models = api_models - AVAILABLE_API_MODELS
  if bad_api_models:
    raise ValueError('requested API models that are not available: {};'
                     '\nthe set of available API models is: {}'.format(
                         bad_api_models, AVAILABLE_API_MODELS))
  return rules, api_models, ensembles


def bot_is_mod(reddit, subreddit):
  try:
    mods = subreddit.moderator()
    return reddit.user.me() in mods
  except Exception:
    return False


def score_subreddit(creds_dict,
                    subreddit_name,
                    rules,
                    api_models,
                    ensembles,
                    should_remove_quotes,
                    output_path=None):
  """Score subreddit commments via Perspective API and apply moderation rules.

  Args:
    creds_dict: (dict) A dictionary of API credentials for Perspective and
                Reddit.
    subreddit_name: (str) The name of the subreddit to stream.
    rules: (list) A list of rules to apply to each comment.
    api_models: (list) A list of models that the API must call to apply rules.
    ensembles: (list) A list of ensemble models based on the API models to
      additionally score each comment with.
    remove_quotes: (bool) Whether to remove Reddit quotes before scoring.
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
      original_comment = comment.body
      comment_for_scoring = (remove_quotes(original_comment)
                             if should_remove_quotes else original_comment)
      if len(comment_for_scoring) > 20000:
        print('Comment too long, skipping...')
        continue
      scores = perspective.score_text(comment_for_scoring, api_models,
                                      language=LANGUAGE)
      for e in ensembles:
        scores[e.name] = e.predict_one(scores)
      if output_path:
        with open(output_path, 'a') as f:
          record = {
              'comment_text': original_comment,
              'scored_comment_text': comment_for_scoring,
              'created_utc': comment.created_utc,
              'permalink': 'https://reddit.com' + comment.permalink,
              'author': comment.author.name,
          }
          record.update(scores)
          json.dump(record, f)
          f.write('\n')

      for rule in rules:
        if rule.check_model_rules(scores):
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
          # TODO(jetpack): would be better to see all rules that trigger, and
          # report once with messages combined. Currenty, we only report things
          # once, according to first rule that applies.
          break
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
  if args.output_dir:
    file_suffix = '%s_%s.json' % (args.subreddit,
                                  datetime.now().strftime('%Y%m%d_%H%M%S'))
    output_path = os.path.join(args.output_dir, file_suffix)

  else:
    output_path = None
  rules, api_models, ensembles = parse_config(args.config_file)
  score_subreddit(creds, args.subreddit, rules, api_models, ensembles,
                  args.remove_quotes, output_path)

if __name__ == '__main__':
  _main()
