import logging
import numpy as np

from flask import current_app, jsonify
from flask_restful import Resource

LOGGER = logging.getLogger(__name__)


def serialize_numpy_data(obj):
    """Recursively convert numpy data types to JSON-serializable types"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.int8, np.int16, np.int32, np.int64, 
                         np.uint8, np.uint16, np.uint32, np.uint64)):
        return int(obj)
    elif isinstance(obj, (np.float16, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {key: serialize_numpy_data(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_numpy_data(item) for item in obj]
    else:
        return obj


def get_prediction_values(models, fm, direct_id=None):
    try:
        if models is None:
            raise ValueError("Models are not loaded")
        if fm is None:
            raise ValueError("Feature matrix is not loaded")
            
        if direct_id is None:
            predictions = models.predict_proba(fm)
        else:
            if direct_id not in fm.index:
                raise ValueError(f"Patient {direct_id} not found in feature matrix")
            predictions = models.predict_proba(fm.loc[direct_id].to_frame().T)
        
        # Apply comprehensive numpy serialization
        return serialize_numpy_data(predictions)
    except Exception as e:
        LOGGER.error(f"Error in get_prediction_values: {str(e)}")
        raise


class Prediction(Resource):

    def get(self, direct_id):
        """
        Get the prediction results of a target patient.
        ---
        tags:
          - prediction
        parameters:
          - name: direct_id
            in: path
            required: true
            schema:
              type: string
            description: the identifier of the patient's related entry in the target entity
                (e.g., the admission id).
        responses:
          200:
            description: The prediction results of the target patient.
            content:
              application/json:
                schema:
                  type: object
                  additionalProperties:
                    type: number
          400:
            $ref: '#/components/responses/ErrorMessage'
          500:
            $ref: '#/components/responses/ErrorMessage'
        """
        try:
            settings = current_app.settings
            LOGGER.info(f"Attempting prediction for patient {direct_id}")
            LOGGER.info(f"Models type: {type(settings.get('models'))}")
            LOGGER.info(f"Feature matrix shape: {settings.get('feature_matrix', 'None').shape if settings.get('feature_matrix') is not None else 'None'}")
            
            res = get_prediction_values(settings["models"], settings['feature_matrix'],
                                        direct_id)
            return res
        except Exception as e:
            LOGGER.exception(f"Error in Prediction.get for patient {direct_id}: {str(e)}")
            return {'message': str(e)}, 500


class AllPrediction(Resource):

    def get(self):
        """
        Get the prediction results of all patients.
        ---
        tags:
          - prediction
        responses:
          200:
            description: The prediction results of all patients.
            content:
              application/json:
                schema:
                  type: object
                  additionalProperties:
                    type: array
                    items:
                      type: number

          400:
            $ref: '#/components/responses/ErrorMessage'
          500:
            $ref: '#/components/responses/ErrorMessage'
        """
        try:
            settings = current_app.settings
            LOGGER.info("Attempting prediction for all patients")
            LOGGER.info(f"Models type: {type(settings.get('models'))}")
            LOGGER.info(f"Feature matrix shape: {settings.get('feature_matrix', 'None').shape if settings.get('feature_matrix') is not None else 'None'}")
            
            res = get_prediction_values(settings["models"], settings['feature_matrix'])
            return res
        except Exception as e:
            LOGGER.exception(f"Error in AllPrediction.get: {str(e)}")
            return {'message': str(e)}, 500
