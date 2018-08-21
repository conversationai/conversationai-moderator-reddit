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

"""An ensemble combines multiple sub-models.

This class is currently just a lightweight wrapper around simple scikit-learn
models. It does not handle training of ensembles, just evaluation.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import pandas as pd

from sklearn import linear_model


class LrEnsemble(object):
  """Logistic regression ensemble."""

  def __init__(self, name, feature_weights, intercept_weight, **lr_kwargs):
    """"Construct a logistic regression ensemble.

    Args:
     name: (string) name for the model.
     feature_weights: (dict string to float) keys are feature column names,
       values are weights.
     intercept_weight: (float) intercept/bias term.
     **lr_kwargs: passed to the scikit-learn LogisticRegression constructor.
    """
    self.name = name
    self._feature_col_names = feature_weights.keys()

    kwargs = {'solver': 'saga'}
    kwargs.update(lr_kwargs)
    lr = linear_model.LogisticRegression(kwargs)
    lr.coef_ = np.array([feature_weights.values()])
    lr.intercept_ = np.array([intercept_weight])
    self._ensemble = lr

  def predict_frame(self, df):
    """Return vector of ensembles scores for each item in DataFrame.

    Args:
      df: (DataFrame) must contain columns corresponding to feature column names
        given during construction.

    Returns:
      Vector of scores from 0 to 1.
    """
    features = df.loc[:, self._feature_col_names]
    scores = self._ensemble.predict_proba(features)
    return scores[:, 1]

  def predict_one(self, feature_values):
    """Return ensemble score for an example with the given feature weights.

    Args:
      feature_values: (dict string to float) must contain keys corresponding to
        feature column names given during construction.

    Returns:
      Float score from 0 to 1.
    """
    df = pd.DataFrame([feature_values])  # single row frame
    scores = self.predict_frame(df)
    return scores[0]


# TODO(jetpack): proper tests would be nice :-)

if __name__ == '__main__':
  e = LrEnsemble('e', {'MODEL_A': 1.2, 'MODEL_B': 3.4, 'MODEL_C': -0.9}, -0.3)

  ex1 = {'MODEL_A': 0.50, 'MODEL_B': 0.92, 'MODEL_C': 0.10}  # high scoring
  ex2 = {'MODEL_A': 0.20, 'MODEL_B': 0.05, 'MODEL_C': 0.85}  # low scoring

  for ex in (ex1, ex2):
    print('example:', ex)
    print('ensemble score:', e.predict_one(ex))
    print('\n===\n')

  df = pd.DataFrame([ex1, ex2])
  df['data'] = ['hello', 'goodbye']
  print('\nboth as a dataframe:\n', df)
  print('\nscores:', e.predict_frame(df))
