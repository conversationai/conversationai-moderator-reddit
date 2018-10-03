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

"""A reddit bot which uses the Perpsective API to help moderate subreddits."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import Counter
import yaml

import ensemble
from perspective_rule import Rule


# TODO(jetpack): maybe move this to perspective_client?
AVAILABLE_API_MODELS = set([
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
])


def _duplicate_items(xs):
  return [x for (x, count) in Counter(items).iteritems()
          if count > 1]


def _has_duplicates(xs):
  return len(xs) != len(set(xs))


def load_rules(rules_config):
  rules = []
  # Note: models mentioned in rules may contain the names of ensemble models.
  models = set()
  # TODO(jetpack): add more validation for comment_features: check that all
  # features are supported and have the right type.
  for r in rules_config:
    rules.append(Rule(r.get('name'),
                      r['perspective_score'],
                      r.get('comment_features', {}),
                      r['action'],
                      r.get('report_reason')))
    models.update(r['perspective_score'].keys())
  assert len(rules) > 0, 'Rules file empty!'
  rule_names = [r.name for r in rules]
  if _has_duplicates(rule_names):
    raise ValueError('Duplicate rule names: {}'.format(
        _duplicate_items(rule_names)))
  return rules, models


def load_ensembles(ensembles_config):
  ensembles = []
  api_models = set()
  for e in ensembles_config:
    ensembles.append(ensemble.LrEnsemble(e['name'], e['feature_weights'],
                                         e['intercept_weight']))
    api_models.update(e['feature_weights'].keys())

  ensemble_names = [e.name for e in ensembles]
  if _has_duplicates(ensemble_names):
    raise ValueError('Duplicate ensemble names! {}'.format(ensemble_names))
  ensembles_with_api_model_names = [e for e in ensemble_names
                                    if e in AVAILABLE_API_MODELS]
  if ensembles_with_api_model_names:
    raise ValueError(
        'Ensembles cannot have the same name as an API model: {}'.format(
            ensembles_with_api_model_names))

  return ensembles, api_models


def parse_config(filepath):
  with open(filepath) as f:
    config = yaml.load(f)

  ensembles, api_models_for_ensembles = [], set()
  if 'ensembles' in config:
    ensembles, api_models_for_ensembles = load_ensembles(config['ensembles'])

  rules, models_for_rules = load_rules(config['rules'])

  ensemble_names = set(e.name for e in ensembles)
  api_models_for_rules = [m for m in models_for_rules
                          if m not in ensemble_names]
  api_models = api_models_for_ensembles.union(api_models_for_rules)
  bad_api_models = api_models - AVAILABLE_API_MODELS
  if bad_api_models:
    raise ValueError('requested API models that are not available: {};'
                     '\nthe set of available API models is: {}'.format(
                         bad_api_models, AVAILABLE_API_MODELS))
  return rules, api_models, ensembles
