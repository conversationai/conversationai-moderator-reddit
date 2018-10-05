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

"""config tests"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

import config



class ConfigTest(unittest.TestCase):

  def test_has_duplicates(self):
    self.assertTrue(config._has_duplicates([1, 1]))
    self.assertFalse(config._has_duplicates([1, 2]))

  def test_duplicate_items(self):
    self.assertEqual([1],
                     config._duplicate_items([1, 1]))
    self.assertEqual([1, 2],
                     config._duplicate_items([1, 2, 1, 2]))
    self.assertEqual([],
                     config._duplicate_items([1, 2]))

  def test_load_rules(self):
    rule_records = [
      { 'perspective_score': { 'm1': '> 0.5' },
        'action': 'report' },
      { 'perspective_score': { 'm1': '> 0.5', 'm2': '> 0.9' },
        'action': 'noop' },
      { 'perspective_score': { 'm3': '> 0.2' },
        'action': 'noop',
        'name': 'third_rule' },
    ]
    rules, models = config._load_rules(rule_records)
    self.assertEqual(set(('m1', 'm2', 'm3')), models)
    self.assertEqual(3, len(rules))
    self.assertEqual('m1', rules[0].name)
    self.assertEqual('m1__m2', rules[1].name)
    self.assertEqual('third_rule', rules[2].name)

  def test_load_rules_fails_on_empty(self):
    with self.assertRaises(ValueError):
      config._load_rules([])

  def test_load_rules_fails_on_missing_action(self):
    rule_record_missing_action = { 'perspective_score': { 'm1': '> 0.1' } }
    with self.assertRaises(KeyError):
      config._load_rules([rule_record_missing_action])

  def test_load_rules_fails_on_missing_scores(self):
    rule_record_missing_scores = { 'action': 'noop' }
    with self.assertRaises(KeyError):
      config._load_rules([rule_record_missing_scores])

  def test_load_rules_fails_on_dupe_names(self):
    rule_records_dupe_names = [
      { 'name': 'hi',
        'perspective_score': { 'm1': '> 0.5' },
        'action': 'report' },
      { 'name': 'hi',
        'perspective_score': { 'm2': '> 0.9' },
        'action': 'noop' },
    ]
    with self.assertRaises(ValueError):
      config._load_rules(rule_records_dupe_names)

  def test_load_rules_fails_on_implicit_dupe_names(self):
    # Causes error because no explicit name and auto-generated name is 'm1' for
    # both.
    rule_records_dupe_names = [
      { 'perspective_score': { 'm1': '> 0.5' },
        'action': 'report' },
      { 'perspective_score': { 'm1': '> 0.9' },
        'action': 'noop' },
    ]
    with self.assertRaises(ValueError):
      config._load_rules(rule_records_dupe_names)

  def test_load_ensembles(self):
    ensemble_records = [
      { 'name': 'e1',
        'feature_weights': {'m1': 1, 'm2': 2},
        'intercept_weight': -1,
      },
      { 'name': 'e2',
        'feature_weights': {'m1': 10, 'm3': 30},
        'intercept_weight': -10,
      },
    ]
    ensembles, api_models = config._load_ensembles(ensemble_records)
    self.assertEqual(set(('m1', 'm2', 'm3')), api_models)
    self.assertEqual(2, len(ensembles))
    self.assertEqual('e1', ensembles[0].name)
    self.assertEqual('e2', ensembles[1].name)

  def test_load_ensembles_fail_on_dupe_names(self):
    ensemble_records = [
      { 'name': 'e1',
        'feature_weights': {'m1': 1, 'm2': 2},
        'intercept_weight': -1,
      },
      { 'name': 'e1',
        'feature_weights': {'m1': 10, 'm3': 30},
        'intercept_weight': -10,
      },
    ]
    with self.assertRaises(ValueError):
      config._load_ensembles(ensemble_records)

  def test_load_ensembles_fail_on_using_api_model_name(self):
    ensemble_records = [
      { 'name': 'TOXICITY',
        'feature_weights': {'m1': 1, 'm2': 2},
        'intercept_weight': -1,
      },
    ]
    with self.assertRaises(ValueError):
      config._load_ensembles(ensemble_records)

  def test_load_config(self):
    config_dict = {
        'rules': [
            { 'perspective_score': { 'TOXICITY': '> 0.5' },
              'action': 'report' },
            { 'perspective_score': { 'e1': '> 0.5' },
              'action': 'noop' },
        ],
        'ensembles': [
            { 'name': 'e1',
              'feature_weights': {'TOXICITY': 1, 'THREAT': 2},
              'intercept_weight': -1 }
        ],
    }
    rules, api_models, ensembles = config._load_config(config_dict)
    self.assertEqual(set(('TOXICITY', 'THREAT')), api_models)
    self.assertEqual(2, len(rules))
    self.assertEqual('TOXICITY', rules[0].name)
    self.assertEqual('e1', rules[1].name)
    self.assertEqual(1, len(ensembles))
    self.assertEqual('e1', ensembles[0].name)

  def test_load_config_fails_on_unknown_api_models(self):
    config_dict = {
        'rules': [
            { 'perspective_score': { 'BLAH_TOXICITY': '> 0.5' },
              'action': 'report' },
        ],
    }
    with self.assertRaises(ValueError) as cm:
      config._load_config(config_dict)
    self.assertIn('requested API models that are not available: BLAH_TOXICITY',
                  str(cm.exception))



if __name__ == '__main__':
    unittest.main()
