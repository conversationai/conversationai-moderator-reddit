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

"""A reddit bot to detect which actions subreddit moderators actually took."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
from datetime import datetime, timedelta
import json
import praw
import time
import sys

from creds import creds
from log_subreddit_comments import append_record, now_timestamp


APPROVED_COL = 'approved'
REMOVED_COL = 'removed'
DELETED_COL = 'deleted'


def write_moderator_actions(reddit,
                            record,
                            id_key,
                            timestamp_key,
                            output_path,
                            hours_to_wait,
                            has_mod_creds):
  bot_scored_time = datetime.strptime(record[timestamp_key], '%Y%m%d_%H%M%S')
  time_to_check = bot_scored_time + timedelta(hours=hours_to_wait)
  wait_until(time_to_check)

  record['action_checked_utc'] = now_timestamp()
  status_fields = check_comment_status(reddit, record[id_key], has_mod_creds)
  if status_fields is not None:
    record.update(status_fields)

  append_record(output_path, record)


def check_comment_status(reddit, comment_id, has_mod_creds):
  try:
    comment = reddit.comment(comment_id)
    return get_comment_status(comment, has_mod_creds)
  except Exception as e:
    print('\nFailed to check comment status due to exception:', e)
    if has_mod_creds:
      print('(Maybe missing moderator credentials?)')
    return None


def get_comment_status(comment, has_mod_creds):
  status = {
      DELETED_COL: comment.author is None and comment.body == '[deleted]'
  }
  if has_mod_creds:
    status[APPROVED_COL] = comment.approved
    status[REMOVED_COL] = comment.removed
  else:
    status[REMOVED_COL] = (comment.author is None
                           and comment.body == '[removed]')
  return status


def wait_until(time_to_proceed):
  """Waits until the current utc datetime is past time_to_proceed"""
  now = datetime.utcnow()
  if now < time_to_proceed:
    time_to_wait = (time_to_proceed - now).seconds
    print('\nWaiting %.1f seconds...' % time_to_wait)
    time.sleep(time_to_wait)


def _main():
  parser = argparse.ArgumentParser(
      'Reads the output of moderate_subreddit.py or log_subreddit_comments.py'
      ' and adds actions taken by human moderators.')
  parser.add_argument('input_path', help='json file with reddit comment ids')
  parser.add_argument('output_path', help='path to write output file')
  parser.add_argument('-id_key', help='json key containing reddit comment id',
                      default='comment_id')
  parser.add_argument('-mod_creds',
                      help=('whether the bot has mod credentials. if set,'
                            ' the output contains "approved", "removed", and'
                            ' "deleted" fields.'),
                      dest='has_mod_creds',
                      action='store_true')
  parser.add_argument('-no_mod_creds',
                      help=('the bot does not have mod credentials. the output'
                            ' only contains "removed" and "deleted" fields,'),
                      dest='has_mod_creds',
                      action='store_false')
  parser.add_argument('-timestamp_key', help='json key containing timestamp'
                      'that moderation bot saw comment',
                      default='bot_scored_utc')
  parser.add_argument('-hours_to_wait',
                      help='the number of hours to wait to allow moderators to'
                      ' respond to bot',
                      type=float,
                      default=12)
  parser.add_argument('-stop_at_eof',
                      help='if set, stops the process once the end of file is '
                      'hit instead of waiting for new comments to be written',
                      action='store_true')
  parser.set_defaults(has_mod_creds=None)
  args = parser.parse_args()
  if args.has_mod_creds is None:
    raise ValueError('must explicitly use either -mod_creds or -no_mod_creds!')

  reddit = praw.Reddit(client_id=creds['reddit_client_id'],
                       client_secret=creds['reddit_client_secret'],
                       user_agent=creds['reddit_user_agent'],
                       username=creds['reddit_username'],
                       password=creds['reddit_password'])

  with open(args.input_path) as f:
    # Loops through the file and waits at EOF for new data to be written.
    while True:
      where = f.tell()
      line = f.readline()
      print('.', end='')
      sys.stdout.flush()
      if line:
        write_moderator_actions(reddit,
                                json.loads(line),
                                args.id_key,
                                args.timestamp_key,
                                args.output_path,
                                args.hours_to_wait,
                                args.has_mod_creds)
      elif args.stop_at_eof:
        return
      else:
        print('\nReached EOF. Waiting for new data...')
        time.sleep(args.hours_to_wait * 3600)
        f.seek(where)


if __name__ == '__main__':
  _main()
