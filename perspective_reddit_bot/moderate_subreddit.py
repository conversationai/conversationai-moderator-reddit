"""A reddit bot which uses the Perpsective API to help moderate subreddits.

Args:
      subreddit: (required) A positional argument for the subreddit to moderate.
      -rule_config_file: (optional) The file which contains moderation rules. Defaults to 'rules.yaml'
      -output_dir: (optional) If set, scores for all streamed commments are written to a file in this directory.
"""

import argparse
import os
import time

import pandas as pd
import praw
import yaml

import perspective_client
import score_dataset
from creds import creds
from perspective_rule import Rule

TEXT_COLUMN = 'comment_text'

LANGUAGE = 'en'
#TODO(nthain): support automated language detection.

def parse_rules(filepath):
  rules = []
  models = []
  with open(filepath) as f:
    raw_rules = yaml.load_all(f)
    for r in raw_rules:
      rules.append(Rule(r['perspective_score'], r['action'], r.get('report_reason')))
      models.extend(r['perspective_score'].keys())
  assert len(rules) > 0, 'Rules file empty!'
  return rules, models

def bot_is_mod(reddit, subreddit):
  mods = subreddit.moderator()
  return reddit.user.me() in mods


def score_subreddit(creds,
                    subreddit_name,
                    rules,
                    models,
                    output_path = None):

  reddit = praw.Reddit(client_id = creds['client_id'],
  					 client_secret = creds['client_secret'],
  					 user_agent = creds['user_agent'],
             username = creds['username'],
             password = creds['password'])
  subreddit = reddit.subreddit(subreddit_name)

  try:
    mod_permissions = bot_is_mod(reddit, subreddit)
  except Exception:
    mod_permissions = False
  if mod_permissions:
    print('Bot is moderator of subreddit.')
    print('Moderation actions will be applied.')
  else:
    print('Bot is not moderator of subreddit.')
    print('Moderation actions will not be applied.')

  perspective = perspective_client.PerspectiveClient(creds['perspective_api_key'])

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
                                                language = LANGUAGE)
      if output_path:
        with open(output_path, 'a') as f:
          scored_df.to_json(f, orient='records', lines=True)

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
      print('Skipping comment due to exception: %s' % str(e))


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
    output_path = os.path.join(args.output_dir, '%s_%s.json' % (args.subreddit, int(time.time())))
  else:
    output_path = None
  rules, models = parse_rules(args.rule_config_file)
  score_subreddit(creds, args.subreddit, rules, models, output_path)

if __name__ == '__main__':
  _main()