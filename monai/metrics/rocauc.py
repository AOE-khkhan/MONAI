# Copyright 2020 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import warnings
import numpy as np
from monai.networks.utils import one_hot


def _calculate(y, y_pred):
    pos_indexes, neg_indexes = list(), list()
    for index, y_ in enumerate(y):
        if y_ == 1:
            pos_indexes.append(index)
        elif y_ == 0:
            neg_indexes.append(index)
        else:
            raise ValueError('labels should be binary values.')

    def compare(a, b):
        if a > b:
            return 1
        elif a == b:
            return 0.5
        else:
            return 0
    auc = sum([sum([compare(y_pred[i], y_pred[j]) for j in neg_indexes]) for i in pos_indexes])

    return auc / (len(pos_indexes) * len(neg_indexes))


def compute_roc_auc(y_pred, y, to_onehot_y=False, add_softmax=False, add_sigmoid=False, average='macro'):
    """Computes Area Under the Receiver Operating Characteristic Curve (ROC AUC) based on:
    `sklearn.metrics.roc_auc_score <http://scikit-learn.org/stable/modules/generated/
    sklearn.metrics.roc_auc_score.html#sklearn.metrics.roc_auc_score>`_ .

    Args:
        y_pred (torch.Tensor): input data to compute, typical classification model output.
            it must be One-Hot format and first dim is batch, example shape: [16] or [16, 2].
        y (torch.Tensor): ground truth to compute ROC AUC metric, the first dim is batch.
            example shape: [16, 1] will be converted into [16, 3].
        to_onehot_y (bool): whether to convert `y` into the one-hot format. Defaults to False.
        add_softmax (bool): whether to add softmax function to y_pred before computation. Defaults to False.
        add_sigmoid (bool): whether to add sigmoid function to y_pred before computation. Defaults to False.
        average: {'macro', 'weighted', 'micro'} or None, type of averaging performed if not binary
        classification. default is 'macro'.
            'macro': calculate metrics for each label, and find their unweighted mean.
                this does not take label imbalance into account.
            'weighted': calculate metrics for each label, and find their average,
                weighted by support (the number of true instances for each label).
            'micro': calculate metrics globally by considering each element of the label
                indicator matrix as a label.
            None: the scores for each class are returned.

    Note:
        ROCAUC expects y to be comprised of 0's and 1's.
        y_pred must either be probability estimates or confidence values.

    """
    if add_softmax and add_sigmoid:
        raise ValueError('add_softmax=True and add_sigmoid=True are not compatible.')

    y_pred_ndim = y_pred.ndimension()
    y_ndim = y.ndimension()
    if y_pred_ndim not in (1, 2):
        raise ValueError("predictions should be of shape (batch_size, n_classes) or (batch_size, ).")
    if y_ndim not in (1, 2):
        raise ValueError("targets should be of shape (batch_size, n_classes) or (batch_size, ).")
    if y_pred_ndim == 2 and y_pred.shape[1] == 1:
        y_pred = y_pred.squeeze(dim=-1)
        y_pred_ndim = 1
    if y_ndim == 2 and y.shape[1] == 1:
        y = y.squeeze(dim=-1)
        y_ndim = 1

    if add_sigmoid:
        y_pred = y_pred.float().sigmoid()

    if y_pred_ndim == 1:
        if to_onehot_y:
            warnings.warn('y_pred has only one channel, to_onehot_y=True ignored.')
        if add_softmax:
            warnings.warn('y_pred has only one channel, add_softmax=True ignored.')
        return _calculate(y, y_pred)
    else:
        n_classes = y_pred.shape[1]
        if to_onehot_y:
            y = one_hot(y, n_classes)
        if add_softmax:
            y_pred = y_pred.float().softmax(dim=1)

        if average == 'micro':
            def flat(x):
                return [i for k in x for i in k]
            return _calculate(flat(y), flat(y_pred))
        else:
            y, y_pred = y.transpose(0, 1), y_pred.transpose(0, 1)
            auc_values = [_calculate(y_, y_pred_) for y_, y_pred_ in zip(y, y_pred)]
            if average is None:
                return auc_values
            if average == 'macro':
                return np.mean(auc_values)
            if average == 'weighted':
                weights = [sum(y_) for y_ in y]
                return np.average(auc_values, weights=weights)
            raise ValueError('unsupported average method.')
