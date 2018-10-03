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

import pandas as pd
from sklearn import metrics

from moderate_subreddit import RULE_OUTCOME_OUTPUT_PREFIX
from perspective_rule import REPORT_ACTION


def get_rule_outcome_columns(df):
  return [x for x in df.columns
          if x.startswith(RULE_OUTCOME_OUTPUT_PREFIX)]


def rule_column_to_name(rule_output_col):
  return rule_output_col[len(RULE_OUTCOME_OUTPUT_PREFIX):]


def process_modactions_frame(df):
  """Returns cleaned dataframe with just rule outcomes and labels."""
  rule_cols = get_rule_outcome_columns(df)
  cooked_df = df.loc[:, ['removed'] + rule_cols].copy()

  # Drop nulls.
  if cooked_df['removed'].isna().any():
    print('Note: dropping {} examples due to missing "removed" field'
          ' (comment may have been deleted?)'.format(
              cooked_df['removed'].isna().sum()))
    cooked_df.dropna(subset=['removed'], inplace=True)

  # Turn rule outcomes into booleans.
  for c in rule_cols:
    cooked_df[c] = cooked_df[c] == REPORT_ACTION

  return cooked_df


def print_basic_info(df):
  print('number of examples:', len(df))
  print('removed examples: {} ({.1f}%)'.format(
      df['removed'].sum(), 100 * df['removed'].sum() / len(df)))


def compute_rule_metrics(df):
  rule_cols = get_rule_outcome_columns(df)
  rows = []
  for rule_col in rule_cols:
    rows.append({
        'rule': rule_column_to_name(rule_col),
        'precision': metrics.precision_score(df['removed'], df[rule_col]),
        'recall': metrics.recall_score(df['removed'], df[rule_col]),
        'flags': df[rule_col].sum(),
    })
  return pd.DataFrame(rows, columns=['rule', 'precision', 'recall', 'flags'])


def _main():
  parser = argparse.ArgumentParser(
      'Reads the output of check_mod_actions.py and outputs metrics for'
      ' configured rules.')
  parser.add_argument('actions_path', help='json file with mod actions')
  args = parser.parse_args()

  raw_df = pd.read_json(args.actions_path, lines=True)
  cleaned_df = prep_modactions_frame(raw_df)

  print_basic_info(cleaned_df)
  print(compute_rule_metrics(df))


if __name__ == '__main__':
  _main()
