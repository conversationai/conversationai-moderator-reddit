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

"""compute_bot_metrics tests"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

import numpy as np
import pandas as pd

import compute_bot_metrics


class ComputeBotMetricsTest(unittest.TestCase):

  def test_process_modactions_frame(self):
    raw_df = pd.DataFrame({
        'removed': [True, False, np.NaN],
        'rule:hitox': ['report', 'noop', 'report'],
        'rule:medtox': ['noop', 'noop', 'rule-not-triggered'],
    })
    cleaned_df = compute_bot_metrics.process_modactions_frame(raw_df)
    # Should drop the last row due to nan in removed.
    self.assertEqual(2, len(cleaned_df))
    # Should convert rule columns to booleans.
    self.assertEqual([True, False], list(cleaned_df['rule:hitox']))
    self.assertEqual([False, False], list(cleaned_df['rule:medtox']))

  def test_compute_rule_metrics(self):
    df = pd.DataFrame({
        'removed': [True, True, False, False],
        'rule:hitox': [True, False, False, False],
        'rule:medtox': [True, True, True, True],
    })
    metrics = compute_bot_metrics.compute_rule_metrics(df)
    expected_df = pd.DataFrame({
        'rule': ['hitox', 'medtox', '~overall~'],
        'precision': [1.0, 0.5, 0.5],
        'recall': [0.5, 1.0, 1.0],
        'flags': [1, 4, 4],
    }, columns=['rule', 'precision', 'recall', 'flags'])
    pd.testing.assert_frame_equal(expected_df, metrics)

  def test_compute_pr_table(self):
    df = pd.DataFrame({
        'removed': [True, True, False, False],
        'score:tox': [1.0, 0.5, 0.6, 0.0],
    })
    pr_table = compute_bot_metrics.compute_pr_table(df, 'score:tox', 10)
    expected_df = pd.DataFrame({
        'precision': [0.6666666666666666, 0.5, 1.0],
        'recall': [1.0, 0.5, 0.5],
        'threshold': [0.5, 0.6, 1.0],
    }, columns=['precision', 'recall', 'threshold'])
    pd.testing.assert_frame_equal(expected_df, pr_table)

if __name__ == '__main__':
    unittest.main()
