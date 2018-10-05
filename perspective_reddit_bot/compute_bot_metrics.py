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

"""A tool to compute performance metrics for the reddit bot."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse

import pandas as pd
from sklearn import metrics

from check_mod_actions import REMOVED_COL
from moderate_subreddit import RULE_OUTCOME_OUTPUT_PREFIX, MODEL_SCORE_OUTPUT_PREFIX
from perspective_rule import REPORT_ACTION


def get_rule_outcome_columns(df):
  return [x for x in df.columns if x.startswith(RULE_OUTCOME_OUTPUT_PREFIX)]


def get_model_score_columns(df):
  return [x for x in df.columns if x.startswith(MODEL_SCORE_OUTPUT_PREFIX)]


def rule_column_to_name(rule_output_col):
  return rule_output_col[len(RULE_OUTCOME_OUTPUT_PREFIX):]


def model_column_to_name(model_score_col):
  return model_score_col[len(MODEL_SCORE_OUTPUT_PREFIX):]


def process_modactions_frame(raw_df):
  """Returns cleaned dataframe with just rule outcomes and labels."""
  cooked_df = raw_df.copy()
  rule_cols = get_rule_outcome_columns(cooked_df)

  # Drop nulls.
  if cooked_df[REMOVED_COL].isna().any():
    print('Note: dropping {} examples due to missing "removed" field'
          ' (comment may have been deleted?)'.format(
              cooked_df[REMOVED_COL].isna().sum()))
    cooked_df.dropna(subset=[REMOVED_COL], inplace=True)

  # Turn rule outcomes into booleans.
  for c in rule_cols:
    cooked_df[c] = cooked_df[c] == REPORT_ACTION

  return cooked_df


def print_basic_info(df):
  print('number of comments:', len(df))
  print('number of removed comments: {} ({:.1f}%)'.format(
      df[REMOVED_COL].sum(), 100 * df[REMOVED_COL].sum() / len(df)))


def compute_rule_metrics(df):
  def metrics_for_rule(rule_col):
    return { 'rule': rule_column_to_name(rule_col),
             'precision': metrics.precision_score(df[REMOVED_COL], df[rule_col]),
             'recall': metrics.recall_score(df[REMOVED_COL], df[rule_col]),
             'flags': df[rule_col].sum() }

  rule_cols = get_rule_outcome_columns(df)

  # This column is used to compute the overall performance of all the bot's
  # rules. The column is true whenever the examples are flagged by *any* of the
  # rules, so this computes precision/recall for the bot as a whole.
  overall_pseudo_rule = RULE_OUTCOME_OUTPUT_PREFIX + '~overall~'
  df = df.copy()
  df[overall_pseudo_rule] = df.loc[:, rule_cols].any(axis=1)

  rows = []
  for rule_col in rule_cols:
    rows.append(metrics_for_rule(rule_col))
  rows.append(metrics_for_rule(overall_pseudo_rule))
  return pd.DataFrame(rows, columns=['rule', 'precision', 'recall', 'flags'])


def compute_pr_table(df, score_col, num_rows):
  precisions, recalls, thresholds = metrics.precision_recall_curve(
      df[REMOVED_COL], df[score_col])
  table = pd.DataFrame({'precision': precisions[:-1],
                        'recall': recalls[:-1],
                        'threshold': thresholds},
                       columns=['precision', 'recall', 'threshold'])
  if len(table) > num_rows:
    table = table[::int(len(table) / num_rows)].reset_index(drop=True)
  return table


def _main():
  parser = argparse.ArgumentParser(
      'Reads the output of check_mod_actions.py and outputs metrics for'
      ' configured rules.')
  parser.add_argument('actions_path', help='json file with mod actions')
  parser.add_argument('-pr_table', nargs='+',
                      help=('output full precision/recall tables for this list'
                            ' of models'))
  parser.add_argument('-pr_table_rows', type=int, default=15,
                      help='number of rows for model precision/recall tables')
  args = parser.parse_args()

  raw_df = pd.read_json(args.actions_path, lines=True)
  cleaned_df = process_modactions_frame(raw_df)

  pd.options.display.float_format = '{:.3f}'.format
  pd.options.display.max_rows = 999

  print('\n')
  print_basic_info(cleaned_df)

  print('\n\nPrecision/recall for configured rules:\n')
  print(compute_rule_metrics(cleaned_df))

  # TODO: This is *not* accurate for rules that make use of comment features
  # (i.e. 'toplevel_only') because the precision/recall is computed using just
  # the model score, not any of the comment features. Computing accurate figures
  # in this case is more complicated - we would need to read the rules config
  # and filter the dataset accordingly.
  if args.pr_table:
    print('\n\n\n\nPrecision/recall tables for models:\n')
    for model_col in (MODEL_SCORE_OUTPUT_PREFIX + x for x in args.pr_table):
      print('\n{} table:'.format(model_column_to_name(model_col)))
      print(compute_pr_table(cleaned_df, model_col, args.pr_table_rows))

if __name__ == '__main__':
  _main()
