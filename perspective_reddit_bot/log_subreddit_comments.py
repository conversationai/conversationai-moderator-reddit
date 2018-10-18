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
from collections import deque
from datetime import datetime
import json
import os
import sys
import time

import praw
import prawcore


FILENAME_OUTPUT_PREFIX = 'logsubredditcomments'


def datetime_timestamp(dt):
  """Returns compact, filename-friendly string representation of datetime."""
  return dt.strftime('%Y%m%d_%H%M%S')


def now_timestamp():
  return datetime_timestamp(datetime.utcnow())


def posix_timestamp(seconds_since_epoch):
  return datetime_timestamp(datetime.utcfromtimestamp(seconds_since_epoch))


def comment_url(comment):
  return 'https://reddit.com' + comment.permalink


def append_records(output_path, records):
  with open(output_path, 'a') as f:
    for r in records:
      json.dump(r, f)
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


_PRAW_INITIAL_COMMENTS = 100
_PRAW_STREAM_ERROR_RETRY_WAIT_SECONDS = 15


def comment_stream(stream):
  """Yields new comments. Handles errors and retries."""
  seen_comment_ids = deque(maxlen=_PRAW_INITIAL_COMMENTS)
  while True:
    try:
      for x in stream.comments():
        if x.id in seen_comment_ids:  # Don't return already-seen comments.
          continue
        seen_comment_ids.append(x.id)
        yield x
    except prawcore.exceptions.ServerError, e:
      print('\n\nERROR while reading comment stream:', e)
      print('Waiting {} seconds before retrying...'.format(
          _PRAW_STREAM_ERROR_RETRY_WAIT_SECONDS))
      time.sleep(_PRAW_STREAM_ERROR_RETRY_WAIT_SECONDS)


def log_subreddit(creds, subreddits, output_dir):
  """Log subreddit commments.

  Args:
    creds: (dict) A dictionary of API credentials for Reddit.
    subreddits: (list of str) names of subreddits to stream.
    output_dir: (str) Comments are saved to this directory.
  """
  all_subs = '+'.join(subreddits)
  output_path_subreddit_part = all_subs
  if len(all_subs) > 50:
    output_path_subreddit_part = '_{}_subs_'.format(len(subreddits))
  output_path = os.path.join(
      output_dir,
      '{}_{}_{}.json'.format(FILENAME_OUTPUT_PREFIX,
                             output_path_subreddit_part,
                             now_timestamp()))
  print('saving comments to:', output_path)

  reddit = praw.Reddit(client_id=creds['reddit_client_id'],
                       client_secret=creds['reddit_client_secret'],
                       user_agent=creds['reddit_user_agent'],
                       username=creds['reddit_username'],
                       password=creds['reddit_password'])
  subreddit = reddit.subreddit(all_subs)

  for i, comment in enumerate(comment_stream(subreddit.stream)):
    try:
      print('.', end='')
      sys.stdout.flush()
      output_record = create_comment_output_record(comment)
      if i % 25 == 0: print_comment(i, output_record)
      append_records(output_path, [output_record])
    except Exception as e:
      print('\n\nEXCEPTION!\nException: {}\nSkipping comment: {}\n', e, comment)


def _read_subreddits_file(filename):
  subs = []
  with open(filename) as f:
    for line in f:
      subs.append(line.strip())
  return subs


def _main():
  parser = argparse.ArgumentParser('A tool to log comments to a subreddit.')
  parser.add_argument('-creds', help='JSON file Reddit/Perspective credentials',
                      default='creds.json')
  parser.add_argument('-output_dir', help=' where to save comments')
  parser.add_argument('-subreddit', help='subreddit to log')
  parser.add_argument('-subreddits_file', help='file with list of subreddits')

  args = parser.parse_args()

  if args.subreddit and args.subreddits_file:
    raise ValueError('Should only use one of -subreddit or -subreddits_file!')
  if not (args.subreddit or args.subreddits_file):
    raise ValueError('Must specify -subreddit or -subreddits_file!')
  if args.subreddit:
    subs = [args.subreddit]
  else:
    subs = _read_subreddits_file(args.subreddits_file)
    if len(subs) > 400:
      # TODO: i got errors with ~600 subreddits. figure out official limits.
      print('Warning: logging many ({}) subreddits.'
            ' This may cause PRAW errors..'.format(len(subs)))

  with open(args.creds) as f:
    creds = json.load(f)


  log_subreddit(creds, subs, args.output_dir)


if __name__ == '__main__':
  _main()
