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

"""Library for scoring datasets in CSV or ndjson format."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import os
import time
import pandas as pd
import perspective_client

# In the scored dataset, the scores are contained in columns beginning with this
# prefix. This is used to distinguish between the score columns and the rest of
# the data in the dataframe.
SCORE_COLUMN_PREFIX = 'score:'

# See https://github.com/conversationai/perspectiveapi/blob/master/api_reference.md#models
_DEFAULT_MODELS = [
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
]

_CSV_FORMAT = 'CSV'
_NDJSON_FORMAT = 'NDJSON'

# TODO(jetpack): do we need other options, like encoding, etc?
def read_input(path, text_column):
  """Reads dataframe from path.
  This function tries to autodetects the input type.
  Args:
    path: Input file type.
    text_column: Column with text data. Used to verify data was read correctly.
  Returns:
    Pandas DataFrame.
  Raises:
    ValueError if text_column wasn't found in the parsed data.
  """
  # Note: we try to parse as JSON first since, in many cases, JSON parses as
  # CSV without errors.
  try:
    df = pd.read_json(path, lines=True, encoding='utf-8')
    format_ = _NDJSON_FORMAT
  except ValueError:
    df = pd.read_csv(path, encoding='utf-8')
    format_ = _CSV_FORMAT
  if text_column not in df:
    raise ValueError('text column {} not found in parsed data. Parsed data had'
                     ' columns: {}'.format(text_column, df.columns.values))
  bad_columns = [c for c in df.columns if c.startswith(SCORE_COLUMN_PREFIX)]
  if bad_columns:
    raise ValueError('Your dataset contains a column with an internal'
                     ' reserved prefix ("{}"). Please rename or remove the'
                     ' following columns in your data: {}'.format(
                         SCORE_COLUMN_PREFIX, bad_columns))
  return df, format_


def write_output(df, path, data_format, header = True):
  """Saves dataframe to output path.
  Args:
    df: DataFrame.
    path: Output path.
    data_format: Either _CSV_FORMAT or _NDJSON_FORMAT.
    header: Whether to write the header to a csv.
  Raises:
    ValueError if data_format is unsupported.
  """
  if data_format == _CSV_FORMAT:
    df.to_csv(path, index=False, encoding='utf-8', header=header)
  elif data_format == _NDJSON_FORMAT:
    df.to_json(path, orient='records', lines=True, encoding='utf-8')
  else:
    raise ValueError('unsupported data_format {}'.format(data_format))


def score_dataframe(df, text_column, models, perspective, language = None):
  """Adds score columns to the given dataframe.
  Args:
    df: DataFrame containing examples.
    text_column: Column in df containing text examples.
    models: Which Perspective models to use.
    language: Language of text. If not given, the API will auto-detect the
      language.
    perspective_client: PerspectiveClient instance.
  Returns: DataFrame with same data in df along with new columns prefixed with
    SCORE_COLUMN_PREFIX containing model scores for each example. Note: if the
    API is unable to analyze some of the examples (unsupported language, too
    much data, etc.), the scores for those examples will be null.
  """
  scores = perspective.score_texts(df[text_column].dropna(), models, language,
                                   raise_on_error=False, do_not_store=True)
  scores = pd.DataFrame({} if x is None else x for x in scores)
  renaming = {col: SCORE_COLUMN_PREFIX + col for col in scores.columns}
  scores.rename(columns=renaming, inplace=True)
  scored_df = pd.concat([df, scores], axis='columns')
  return scored_df


def _main():
  """Read dataset, score, and output combined dataframe."""
  parser = argparse.ArgumentParser('Tool to score a CSV or ndjson dataset.')
  parser.add_argument('-api_key', help='Perspective API key', required=True)
  parser.add_argument('-input', help='Path to dataset', required=True)
  parser.add_argument('-output', help='Path for scored dataset', required=True)
  parser.add_argument('-overwrite', help='Overwrite output if it exists',
                      action='store_true')
  parser.add_argument('-models', nargs='+', help='Models to request',
                      default=_DEFAULT_MODELS)
  parser.add_argument('-text_column',
                      help='Column of dataset containing text to score',
                      required=True)
  parser.add_argument('-language',
                      help=('Language of dataset. If not specified, API tries to'
                            ' auto-detect the language.'))
  args = parser.parse_args()
  if os.path.exists(args.output):
    if args.overwrite:
      print('NOTE: output path already exists! Data will be overwritten.')
    else:
      raise RuntimeError(
          'Output path {} already exists. Pass -overwrite if overwriting'
          ' existing data is okay.'.format(args.output))
  print('reading input {}...'.format(args.input))
  input_df, data_format = read_input(args.input, args.text_column)
  print('read {} examples in {} format'.format(len(input_df), data_format))
  print('\ncreating Perspective API client with API key {}...'.format(
      args.api_key))
  perspective = perspective_client.PerspectiveClient(args.api_key)
  print('\nscoring dataset...')
  start = time.time()
  scored_df = score_dataframe(input_df, args.text_column, args.models,
                              args.language, perspective)
  elapsed = time.time() - start
  print('\ntook {:.1f} seconds. Average qps: {:.1f}'.format(
      elapsed, len(input_df) / elapsed))
  print('\nsaving scored dataset to {}...'.format(args.output))
  write_output(scored_df, args.output, data_format)
  print('\nall done!')


if __name__ == '__main__':
  _main()
