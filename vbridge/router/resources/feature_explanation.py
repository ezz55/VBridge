import logging

import pandas as pd
import numpy as np
from flask import current_app, jsonify
from flask_restful import Resource, reqparse

LOGGER = logging.getLogger(__name__)


def get_shap_values(model_manager, direct_id, target=None):
    """Get the SHAP values of features.

    Args:
        model_manager: ModelManager, an object containing all prediction models
        direct_id: the identifier of the patient's related entry in the target entity
                (e.g., the admission id).
        target: the identifier of the prediction target

    Returns:
        A dict mapping prediction target to features' SHAP values for this prediction.
    """
    try:
        shap_values = model_manager.explain(id=direct_id, target=target)
        if target is None:
            return {target: sv.iloc[0].to_dict() if len(sv) > 0 else {} for target, sv in shap_values.items()}
        else:
            # Use iloc[0] to get the first row regardless of index, or direct_id if it exists
            if len(shap_values) > 0:
                if direct_id in shap_values.index:
                    return shap_values.loc[direct_id].to_dict()
                else:
                    return shap_values.iloc[0].to_dict()
            else:
                return {}
    except Exception as e:
        LOGGER.warning(f"Failed to get SHAP values for patient {direct_id}: {str(e)}")
        return {}


def get_what_if_shap_values(fm, model_manager, direct_id, target=None):
    """Perturb the out-of-distribution feature values into the normal range and get the updated
    prediction and SHAP values.

    Args:
        fm: pd.DataFrame, the feature values for all instances
        model_manager: ModelManager, an object containing all prediction models
        direct_id: the identifier of the patient's related entry in the target entity
                (e.g., the admission id).
        target: the identifier of the prediction target

    Returns:
        A dict mapping prediction target to its updated predictions and shap values.
    """
    try:
        shap_values = {}
        targets = model_manager.models.keys() if target is None else [target]
        
        # Only compute statistics on numeric columns
        numeric_cols = fm.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            # No numeric columns, return empty result
            return {} if target is not None else {t: {} for t in targets}
        
        # Compute statistics only on numeric columns
        numeric_fm = fm[numeric_cols]
        stat = numeric_fm.agg(['mean', 'count', 'std']).T
        stat['low'] = stat['mean'] - stat['std'] * 1.96
        stat['high'] = stat['mean'] + stat['std'] * 1.96

        target_fv = fm.loc[direct_id]

        for target in targets:
            shap_task = {}
            # Only consider numeric features for perturbation
            numeric_target_fv = target_fv[numeric_cols]
            
            # Prepare the data for out-of-distribution high values
            high_features = numeric_target_fv[numeric_target_fv > stat['high']].index
            if len(high_features) > 0:
                high_fm = pd.DataFrame(target_fv.values.repeat(len(high_features))
                                       .reshape(-1, len(high_features)),
                                       columns=high_features, index=fm.columns)
                # Perturb the out-of-distribution high values the 'high' boundary
                for feature in high_features:
                    high_fm.loc[feature, feature] = stat.loc[feature]['high']
                # Get the predictions and shap values for the perturbed features
                explanations = model_manager.explain(X=high_fm.T, target=target)
                predictions = model_manager.predict_proba(X=high_fm.T)[target]
                for i, feature in enumerate(high_features):
                    shap_task[feature] = {'shap': explanations.loc[i, feature],
                                          'prediction': predictions[i]}

            # Prepare the data for out-of-distribution low values
            low_features = numeric_target_fv[numeric_target_fv < stat['low']].index
            if len(low_features) > 0:
                low_fm = pd.DataFrame(target_fv.values.repeat(len(low_features))
                                      .reshape(-1, len(low_features)),
                                      columns=low_features, index=fm.columns)
                # Perturb the out-of-distribution low values the 'low' boundary
                for feature in low_features:
                    low_fm.loc[feature, feature] = stat.loc[feature]['low']
                # Get the predictions and shap values for the perturbed features
                explanations = model_manager.explain(X=low_fm.T, target=target)
                predictions = model_manager.predict_proba(X=low_fm.T)[target]
                for i, feature in enumerate(low_features):
                    shap_task[feature] = {'shap': explanations.loc[i, feature],
                                          'prediction': predictions[i]}
            shap_values[target] = shap_task
        
        if target is not None:
            shap_values = shap_values[target]
        return shap_values
    except Exception as e:
        LOGGER.warning(f"What-if SHAP failed for patient {direct_id}: {str(e)}")
        return {} if target is not None else {t: {} for t in (model_manager.models.keys() if target is None else [target])}


class ShapValues(Resource):
    def __init__(self):
        parser_get = reqparse.RequestParser(bundle_errors=True)
        parser_get.add_argument('target', type=str, location='args')
        self.parser_get = parser_get

    def get(self, direct_id):
        """
        Get the SHAP explanations of a patient.
        ---
        tags:
          - explanation
        parameters:
          - name: direct_id
            in: path
            schema:
              type: string
            required: true
            description: the identifier of the patient's related entry in the target entity
                (e.g., the admission id).
          - name: target
            in: query
            schema:
              type: string
            description: the identifier of the target prediction problem (e.g., mortality).
        responses:
          200:
            description: The SHAP explanations.
            content:
              application/json:
                schema:
                  type: object
                  additionalProperties:
                    type: object
                    additionalProperties:
                      type: number
          400:
            $ref: '#/components/responses/ErrorMessage'
          500:
            $ref: '#/components/responses/ErrorMessage'
        """
        try:
            args = self.parser_get.parse_args()
            target = args.get('target', None)
        except Exception as e:
            LOGGER.exception(str(e))
            return {'message': str(e)}, 400

        try:
            settings = current_app.settings
            res = get_shap_values(settings['models'], direct_id, target)
            res = jsonify(res)
        except Exception as e:
            LOGGER.exception(e)
            return {'message': str(e)}, 500
        else:
            return res


class WhatIfShapValues(Resource):
    def __init__(self):
        parser_get = reqparse.RequestParser(bundle_errors=True)
        parser_get.add_argument('target', type=str, location='args')
        self.parser_get = parser_get

    def get(self, direct_id):
        """
        Modify the out-of-reference-range features to the closet normal values one by one and
        get the updated predictions and SHAP explanations.
        ---
        tags:
          - explanation
        parameters:
          - name: direct_id
            in: path
            schema:
              type: string
            required: true
            description: the identifier of the patient's related entry in the target entity
                (e.g., the admission id).
          - name: target
            in: query
            schema:
              type: string
            description: the identifier of the target prediction problem (e.g., mortality).
        responses:
          200:
            description: The predictions and SHAP explanations of the perturbed features.
            content:
              application/json:
                schema:
                  $ref: '#/components/schemas/WhatIfSHAP'
          400:
            $ref: '#/components/responses/ErrorMessage'
          500:
            $ref: '#/components/responses/ErrorMessage'
        """
        try:
            args = self.parser_get.parse_args()
            target = args.get('target', None)
        except Exception as e:
            LOGGER.exception(str(e))
            return {'message': str(e)}, 400

        try:
            settings = current_app.settings
            res = get_what_if_shap_values(settings['feature_matrix'], settings['models'],
                                          direct_id, target)
            res = jsonify(res)
        except Exception as e:
            LOGGER.exception(e)
            return {'message': str(e)}, 500
        else:
            return res
