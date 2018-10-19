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


# TODO: This implementation of batching is a bit complex: read_lines yields
# sentinel values at regular intervals so that read_batches is able to yield
# batches within max_batch_delay. The issue is that when reading from the end of
# the file, there could be an indeterminate amount of time until the next line,
# which would cause accumulated lines to be "stranded".
#
# This can almost certainly be done in a simpler way...

def read_lines(input_path, stop_at_eof, yield_every_period, sentinel):
  """Read lines from file.

  Args:
    input_path: (str) where to read from
    stop_at_eof: (bool) returns reaching end of file if true.
    yield_every_period: (timedelta) yields sentinel value every time period if
        stream doesn't have contents.
    sentinel: value yielded every yield_every_period

  Yields: lines from input_path, or sentinel values
  """
  with open(input_path) as f:
    last_time = datetime.utcnow()
    while True:
      now = datetime.utcnow()
      where = f.tell()
      line = f.readline()
      if line:
        print('.', end='')
        sys.stdout.flush()
        yield line
        last_time = now
      elif stop_at_eof:
        print('\nread_lines stopping due to stop_at_eof.')
        return
      elif now - last_time > yield_every_period:
        yield sentinel
        last_time = now
      else:
        print('\n(eof, waiting {})'.format(yield_every_period))
        time.sleep(yield_every_period.total_seconds())
        f.seek(where)


_PRAW_BATCH_SIZE = 100


def read_batches(input_path, stop_at_eof, max_batch_delay):
  """Yields batches from input_path."""
  current_batch = []
  last_yield_time = datetime.utcnow()
  sentinel = object()
  # read_lines may yield a line right before the max_batch_delay is reached,
  # so we divide the delay by 2 to ensure we get batches out within
  # max_batch_delay.
  for line in read_lines(input_path, stop_at_eof, max_batch_delay/2, sentinel):
    now = datetime.utcnow()
    if line is not sentinel:
      current_batch.append(line)
    if (current_batch
        and (len(current_batch) == _PRAW_BATCH_SIZE
             or now - last_yield_time > max_batch_delay)):
      print('batch(', len(current_batch), ')')
      yield current_batch
      current_batch = []
      last_yield_time = now

  # read_lines exited
  if current_batch:
    yield current_batch


def read_records_with_wait(input_path, stop_at_eof, max_batch_delay,
                           timestamp_key, wait_delta):
  """Yields batches, waiting until all items are old enough."""
  for batch in read_batches(input_path, stop_at_eof, max_batch_delay):
    records = [json.loads(line) for line in batch]
    youngest = max(r[timestamp_key] for r in records)
    create_time_utc = datetime.strptime(youngest, '%Y%m%d_%H%M%S')
    wait_until(create_time_utc + wait_delta)
    yield records


# reddit.info() requires 'fullname' IDs. Comment fullname IDs include a
# 't1_' prefix.
def prefix_comment_id(i):
  """Return 'fullname' version of ID (includes Reddit type prefix)."""
  return i if i.startswith('t1_') else 't1_' + i


# TODO: this function is complicated because reddit.info() _may_ omit data
# (i.e. given 100 comments, it may return fewer than 100 Comment objects). so,
# there's extra bookkeeping to check for dropped records. if this ~never
# happens, we can simplify this code significantly.
def check_mod_actions(output_path, reddit, comments, id_key, has_mod_creds):
  comment_ids = [prefix_comment_id(c[id_key]) for c in comments]
  statuses = fetch_comment_statuses(reddit, comment_ids, has_mod_creds)

  # Index comments by ID so we can attach the status data to the comment
  # records. (Cannot simply zip comments with statuses, since reddit.info() may
  # drop records.)
  comments_by_id = {c[id_key]: c for c in comments}
  for comment_id, status in statuses:
    if not comment_id or not status:
      continue
    if comment_id not in comments_by_id:
      print('BUG: status comment ID not in comments_by_id, dupe?', comment_id)
      continue
    comment = comments_by_id[comment_id]
    comment.update(status)
    comment['action_checked_utc'] = log_subreddit_comments.now_timestamp()
    # Remove from record keeping so we can detect if there are leftover comments
    # for which we failed to fetch the status.
    del comments_by_id[comment_id]
  if comments_by_id:
    print('BUG: {} comments did not have status data. ids: {}'.format(
        len(comments_by_id), list(comments_by_id.keys())))

  log_subreddit_comments.append_records(output_path, comments)


def fetch_comment_statuses(reddit, comment_ids, has_mod_creds):
  try:
    return (get_comment_status(c, has_mod_creds)
            for c in reddit.info(comment_ids))
  except Exception as e:
    print('\nERROR: Failed to fetch comment statuses:', e)
    if has_mod_creds:
      print('(Maybe missing moderator credentials?)')
    return []

def get_comment_status(comment, has_mod_creds):
  try:
    status = {
        DELETED_COL: comment.author is None and comment.body == '[deleted]',
        SCORE_COL: comment.score,
        UPS_COL: comment.ups,
        DOWNS_COL: comment.downs,
        SCORE_HIDDEN_COL: comment.score_hidden,
        COLLAPSED_COL: comment.collapsed,
    }
    # TODO: This is a bit hairy, and I'm not confident it's fully correct. Need to
    # do more extensive, careful testing for comments that are
    # approved-by-moderator, removed-by-moderator, and deleted-by-user when the
    # bot user has mod privileges and when it doesn't have mod privileges.
    if has_mod_creds:
      status[APPROVED_COL] = comment.approved
      status[REMOVED_COL] = comment.removed
    else:
      status[REMOVED_COL] = (comment.author is None
                             and comment.body == '[removed]')
    return comment.id, status
  except Exception as e:
    print('\nERROR: failed to get comment status:', e)
    return None, None


def wait_until(time_to_proceed_utc):
  """Waits until the current utc datetime is past time_to_proceed"""
  now = datetime.utcnow()
  if now < time_to_proceed_utc:
    wait_delta = time_to_proceed_utc - now
    print('\nWaiting for {}...'.format(wait_delta))
    time.sleep(wait_delta.total_seconds())


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

  for comments in read_records_with_wait(
      args.input_path, args.stop_at_eof,
      timedelta(seconds=args.batch_delay_secs),
      args.timestamp_key, timedelta(hours=args.hours_to_wait)):
    check_mod_actions(output_path, reddit, comments, args.id_key,
                      args.has_mod_creds)


if __name__ == '__main__':
  _main()
