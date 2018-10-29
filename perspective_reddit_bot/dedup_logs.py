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

"""Tool for deduping records from logs.

Dupe records can happen because the praw subreddit stream API will give 100
recent comments on startup.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
from collections import deque
import json
import os
import sys

import pandas as pd


def check_counts(expected_total, expected_unique, actual_total, actual_unique):
  error = False
  if expected_total != actual_total:
    print('unexpected total: {} != {}'.format(actual_total, expected_total))
    error = True
  if expected_unique != actual_unique:
    print('unexpected deduped: {} != {}'.format(actual_unique, expected_unique))
    error = True
  if error:
    raise ValueError('counts did not line up');


def pandas_dedup(in_path, out_path, id_col, expected_total, expected_unique):
  """Write deduplicated data. Loads full data into memory."""
  df = pd.read_json(in_path, lines=True)
  deduped = df.drop_duplicates(subset=[id_col])
  print('orig data: \t', len(df))
  print('deduped data: \t', len(deduped))
  print('dropped: \t', len(df) - len(deduped))
  check_counts(expected_total, expected_unique, len(df), len(deduped))
  deduped.to_json(out_path, lines=True, orient='records')


def dedup_stream(in_stream, id_col, window, expected_total, expected_unique):
  """Read from in_stream and yield non-duplicate records within window."""
  seen_ids = deque(maxlen=window)
  yielded = 0
  dupes = 0
  for line in in_stream:
    rec_id = json.loads(line)[id_col]
    if rec_id in seen_ids:
      dupes += 1
    else:
      yielded += 1
      seen_ids.append(rec_id)
      yield line
  print('dedup_stream done. {} records, {} unique, {} dupes.'.format(
      yielded + dupes, yielded, dupes))
  check_counts(expected_total, expected_unique, yielded + dupes, yielded)


def dedup_within_window(in_path, out_path, id_col, window, expected_total,
                        expected_unique):
  with open(in_path) as in_file:
    with open(out_path, 'w') as out_file:
      for line in dedup_stream(in_file, id_col, window, expected_total,
                               expected_unique):
        out_file.write(line)


def get_output_path_from_input(input_path):
  dirname = os.path.dirname(input_path)
  basename = os.path.basename(input_path)
  return os.path.join(dirname, 'deduped__' + basename)


def get_counts(handle, id_col):
  """Print total and unique records. Used to sanity check dedup results."""
  ids = set()
  total = 0
  for line in handle:
    total += 1
    ids.add(json.loads(line)[id_col])
  print(' total:', total)
  print('unique:', len(ids))
  return total, len(ids)


def _main():
  parser = argparse.ArgumentParser('Dedups log data.')
  parser.add_argument('-input_path', help='json file with reddit comment ids',
                      required=True)
  parser.add_argument('-output_path', help='path to write output file')
  parser.add_argument('-id_key', help='json key containing reddit comment id',
                      default='comment_id')
  parser.add_argument('-window',
                      help='how far to look for dupes. 0 to read everything',
                      type=int, default=500)
  args = parser.parse_args()

  with open(args.input_path) as in_handle:
    total, unique = get_counts(in_handle, args.id_key)
  if total == unique:
    print('total == unique {}, no deduping required'.format(unique))
    sys.exit(0)

  output_path = args.output_path or get_output_path_from_input(args.input_path)
  if os.path.exists(output_path):
    raise ValueError('Output filename exists already: ' + output_path)

  if args.window == 0:
    pandas_dedup(args.input_path, output_path, args.id_key, total, unique)
  else:
    dedup_within_window(args.input_path, output_path, args.id_key, args.window,
                        total, unique)


if __name__ == '__main__':
  _main()
