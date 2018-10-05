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

"""Tool to log comments to a subreddit."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
from datetime import datetime
import json
import os
import sys

import praw

from creds import creds


def datetime_timestamp(dt):
  """Returns compact, filename-friendly string representation of datetime."""
  return dt.strftime('%Y%m%d_%H%M%S')


def now_timestamp():
  return datetime_timestamp(datetime.now())


def posix_timestamp(seconds_since_epoch):
  return datetime_timestamp(datetime.utcfromtimestamp(seconds_since_epoch))


def comment_url(comment):
  return 'https://reddit.com' + comment.permalink


def append_record(output_path, record):
  with open(output_path, 'a') as f:
    json.dump(record, f)
    f.write('\n')


def create_comment_output_record(comment):
  return {
      'comment_id': comment.id,
      'link_id': comment.link_id,  # id of the post
      'parent_id': comment.parent_id,
      'subreddit': str(comment.subreddit),
      'permalink': comment_url(comment),
      'orig_comment_text': comment.body,
      'author': comment.author.name,
      'created_utc': posix_timestamp(comment.created_utc),
      'bot_scored_utc': now_timestamp(),
  }


def print_comment(i, record):
  print('\n\n#', i)
  print('url:', record['permalink'])
  print('comment:\n ', record['orig_comment_text'], '\n\n')


def log_subreddit(creds, subreddit_name, output_dir):
  """Log subreddit commments.

  Args:
    creds: (dict) A dictionary of API credentials for Reddit.
    subreddit_name: (str) The name of the subreddit to stream.
    output_dir: (str) Comments are saved to this directory.
  """
  output_path = os.path.join(
      output_dir,
      'logsubreddit_comments_{}_{}.json'.format(subreddit_name,
                                                now_timestamp()))
  print('saving comments to:', output_path)

  reddit = praw.Reddit(client_id=creds['reddit_client_id'],
                       client_secret=creds['reddit_client_secret'],
                       user_agent=creds['reddit_user_agent'],
                       username=creds['reddit_username'],
                       password=creds['reddit_password'])
  subreddit = reddit.subreddit(subreddit_name)

  for i, comment in enumerate(subreddit.stream.comments()):
    try:
      print('.', end='')
      sys.stdout.flush()
      output_record = create_comment_output_record(comment)
      if i % 25 == 0: print_comment(i, output_record)
      append_record(output_path, output_record)
    except Exception as e:
      print('\n\nEXCEPTION!\nException: {}\nSkipping comment: {}\n', e, comment)


def _main():
  parser = argparse.ArgumentParser('A tool to log comments to a subreddit.')
  parser.add_argument('output_dir', help=' where to save comments')
  parser.add_argument('subreddit', help='subreddit to moderate')
  args = parser.parse_args()

  log_subreddit(creds, args.subreddit, args.output_dir)


if __name__ == '__main__':
  _main()
