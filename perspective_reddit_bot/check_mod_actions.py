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
import os
import praw
import time
import sys

import log_subreddit_comments
import moderate_subreddit


# approved, removed, and deleted columns are booleans. 'approved' is only
# present when the bot is a mod.
APPROVED_COL = 'approved'
REMOVED_COL = 'removed'
DELETED_COL = 'deleted'
# score, ups, and downs refer to user votes. in practice, it appears that
# 'downs' is always 0 and 'score' == 'ups'. (this may be different if the bot is
# a mod.)
SCORE_COL = 'score'
UPS_COL = 'ups'
DOWNS_COL = 'downs'
SCORE_HIDDEN_COL = 'score_hidden'
# collapsed is a boolean. it appears to be true when the comment (and all its
# children) are collapsed in the UI. this most commonly happens when the comment
# is deleted or removed, but it also seems to happens when the comment has more
# downvotes
COLLAPSED_COL = 'collapsed'

FILENAME_OUTPUT_PREFIX = 'modactions'


def read_lines(input_path, stop_at_eof, max_batch_delay_secs):
  """Yields lines from input_path. Stops when reaching end if stop_at_eof."""
  with open(input_path) as f:
    while True:
      where = f.tell()
      line = f.readline()
      if line:
        print('.', end='')
        sys.stdout.flush()
        yield json.loads(line)
      elif stop_at_eof:
        print('read_lines stopping due to stop_at_eof!')
        return
      else:
        print('\nEOF. Waiting...')
        time.sleep(max_batch_delay_secs)
        yield None  # HACK!!!
        f.seek(where)


_PRAW_BATCH_SIZE = 100


# TODO(jetpack): this is broken!!!! the event stream is new lines being present.
# this is fine for active streams, but for inactive streams, data can be
# stranded in current_batch for longer than max_batch_delay_secs. use coroutines
# instead?
def read_batches_immediate(input_path, stop_at_eof, max_batch_delay_secs):
  """Yields batches from input_path."""
  current_batch = []
  last_yield_time = datetime.utcnow()
  for line in read_lines(input_path, stop_at_eof, max_batch_delay_secs):
    now = datetime.utcnow()

    # HACK!!!
    if line is not None:
      print('_', end='')
      sys.stdout.flush()
      current_batch.append(line)
    # TODO: replace max_batch_delay_secs with timedelta object.
    if (current_batch
        and (len(current_batch) == _PRAW_BATCH_SIZE
             or (now - last_yield_time).seconds > max_batch_delay_secs)):
      print('\nread_batches: yielding batch! last yield:', last_yield_time)
      yield current_batch
      current_batch = []
      last_yield_time = now

  # read_lines exited
  if current_batch:
    yield current_batch


def read_batches_with_wait(input_path, stop_at_eof, hours_to_wait,
                            max_batch_delay_secs, timestamp_key):
  """Yields batches, waiting until all items are old enough."""
  for batch in read_batches_immediate(input_path, stop_at_eof,
                                      max_batch_delay_secs):
    print('|', end='')
    sys.stdout.flush()
    youngest = max(r[timestamp_key] for r in batch)
    create_time_utc = datetime.strptime(youngest, '%Y%m%d_%H%M%S')
    # TODO: replace hours_to_wait with timedelta object.
    check_time_utc = create_time_utc + timedelta(hours=hours_to_wait)
    wait_until(check_time_utc)
    yield batch


def prefix_comment_id(i):
  return i if i.startswith('t1_') else 't1_' + i


def check_mod_actions(output_path,
                      reddit,
                      comments,
                      id_key,
                      has_mod_creds):
  print('checking mod actions for', len(comments), ' comments...')
  comment_ids = [prefix_comment_id(c[id_key]) for c in comments]
  # TODO: maybe don't do list. needed for len(statuses)
  statuses = list(fetch_comment_statuses(reddit, comment_ids, has_mod_creds))
  print('...got statuses:', len(statuses))

  comments_by_id = {c[id_key]: c for c in comments}
  if len(statuses) != len(comments):
    print('BUG: number of statuses does not match number of comments:',
          len(statuses), len(comments))
  for status in statuses:
    if not status:
      print('BUG: status was empty?')
      continue
    comment_id = status['id']
    if comment_id not in comments_by_id:
      print('BUG: status comment ID not in comments_by_id, dupe?', comment_id)
      continue
    comment = comments_by_id[comment_id]
    del status['id']
    comment.update(status)
    comment['action_checked_utc'] = log_subreddit_comments.now_timestamp()
    del comments_by_id[comment_id]
  if comments_by_id:
    print('BUG: {} comments did not have status data. ids: {}'.format(
        len(comments_by_id), ', '.join(comments_by_id.keys())))

  log_subreddit_comments.append_records(output_path, comments)


def fetch_comment_statuses(reddit, comment_ids, has_mod_creds):
  try:
    return (get_comment_status(c, has_mod_creds)
            for c in reddit.info(comment_ids))
  except Exception as e:
    print('\nFailed to fetch comment statuses due to exception:', e)
    if has_mod_creds:
      print('(Maybe missing moderator credentials?)')
    return []


# TODO: This is a bit hairy, and I'm not confident it's fully correct. Need to
# do more extensive, careful testing for comments that are
# approved-by-moderator, removed-by-moderator, and deleted-by-user when the bot
# user has mod privileges and when it doesn't have mod privileges.
def get_comment_status(comment, has_mod_creds):
  status = {
      'id': comment.id,
      DELETED_COL: comment.author is None and comment.body == '[deleted]',
      SCORE_COL: comment.score,
      UPS_COL: comment.ups,
      DOWNS_COL: comment.downs,
      SCORE_HIDDEN_COL: comment.score_hidden,
      COLLAPSED_COL: comment.collapsed,
  }
  if has_mod_creds:
    status[APPROVED_COL] = comment.approved
    status[REMOVED_COL] = comment.removed
  else:
    status[REMOVED_COL] = (comment.author is None
                           and comment.body == '[removed]')
  return status


def wait_until(time_to_proceed_utc):
  """Waits until the current utc datetime is past time_to_proceed"""
  now = datetime.utcnow()
  if now < time_to_proceed_utc:
    seconds_to_wait = (time_to_proceed_utc - now).seconds
    print('\nWaiting %.1f seconds...' % seconds_to_wait)
    time.sleep(seconds_to_wait)


def drop_prefix(s, pre):
  if s.startswith(pre):
    return s[len(pre):]
  return None


# Try to return an output filename based on input filename.
def get_output_filename_from_input(in_file, hours_to_wait):
  if int(hours_to_wait) == hours_to_wait:
    # Drop ".0" suffix when included in filename.
    hours_to_wait = int(hours_to_wait)
  dirname = os.path.dirname(in_file)
  basename = os.path.basename(in_file)

  bare_basename = drop_prefix(
      basename, log_subreddit_comments.FILENAME_OUTPUT_PREFIX)
  if bare_basename is None:
    bare_basename = drop_prefix(
        basename, moderate_subreddit.FILENAME_OUTPUT_PREFIX)
  if bare_basename is None:
    raise ValueError(
        'Failed to figure out an output path. Specify -output_path explicitly.')
  out_path = os.path.join(
      dirname, '{}_{}delay{}'.format(FILENAME_OUTPUT_PREFIX, hours_to_wait,
                                     bare_basename))
  print('Auto-generated output path:', out_path)
  return out_path


def _main():
  parser = argparse.ArgumentParser(
      'Reads the output of moderate_subreddit.py or log_subreddit_comments.py'
      ' and adds actions taken by human moderators.')
  parser.add_argument('-input_path', help='json file with reddit comment ids',
                      required=True)
  parser.add_argument('-output_path', help='path to write output file')
  parser.add_argument('-creds', help='JSON file Reddit/Perspective credentials',
                      default='creds.json')
  parser.add_argument('-batch_delay_secs',
                      help='max time to delay each request batch',
                      type=float,
                      default=60)
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
  parser.add_argument('-id_key', help='json key containing reddit comment id',
                      default='comment_id')
  parser.add_argument('-timestamp_key',
                      help='json key for timestamp when comment was created',
                      default='created_utc')
  parser.add_argument('-hours_to_wait',
                      help='hours to wait before checking action',
                      type=float,
                      default=24)
  parser.add_argument('-stop_at_eof',
                      help='if set, stops the process once the end of file is '
                      'hit instead of waiting for new comments to be written',
                      action='store_true')
  parser.set_defaults(has_mod_creds=None)
  args = parser.parse_args()

  if args.has_mod_creds is None:
    raise ValueError('must explicitly use either -mod_creds or -no_mod_creds!')

  output_path = (args.output_path
                 or get_output_filename_from_input(args.input_path,
                                                   args.hours_to_wait))
  if os.path.exists(output_path):
    raise ValueError('Output filename exists already: {}'.format(output_path))

  with open(args.creds) as f:
    creds = json.load(f)

  reddit = praw.Reddit(client_id=creds['reddit_client_id'],
                       client_secret=creds['reddit_client_secret'],
                       user_agent=creds['reddit_user_agent'],
                       username=creds['reddit_username'],
                       password=creds['reddit_password'])

  for batch in read_batches_with_wait(
      args.input_path, args.stop_at_eof, args.hours_to_wait,
      args.batch_delay_secs, args.timestamp_key):
    check_mod_actions(output_path, reddit, batch, args.id_key,
                      args.has_mod_creds)


if __name__ == '__main__':
  _main()
