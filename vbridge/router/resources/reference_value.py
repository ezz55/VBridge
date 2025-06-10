import logging

import numpy as np
from flask import current_app, jsonify
from flask_restful import Resource

LOGGER = logging.getLogger(__name__)


def get_reference_values_by_entity(es, entity_id, schema, subject_ids=None):
    """Get the reference values for each item in the required entity.

    Args:
        es: featuretools.EntitySet, the entity set that includes all patients' health records.
        entity_id: string, the identifier of the required entity
        schema: dict, the schema of the entities.
        subject_ids: list, the indexes of the relevant cohort where the reference values are
            derived.

    Returns:
        A dict describing the reference values for each item in the required entity.
    """
    entity_info = schema[entity_id]
    df = es[entity_id]
    # TODO: filter by time
    if subject_ids is not None:
        df = df[df['SUBJECT_ID'].isin(subject_ids)]
    references = {}
    columns = entity_info.get('value_indexes', [])
    for group in df.groupby(entity_info.get('item_index')):
        item_name = group[0]
        item_references = {}
        for col in columns:
            mean, count, std = group[1][col].agg(['mean', 'count', 'std'])
            item_references[col] = {
                'mean': 0 if np.isnan(mean) else mean,
                'std': 0 if np.isnan(std) else std,
                'count': 0 if np.isnan(count) else count,
                'ci95': [0 if np.isnan(mean - 1.96 * std) else (mean - 1.96 * std),
                         0 if np.isnan(mean + 1.96 * std) else (mean + 1.96 * std)]
            }
            references[item_name] = item_references
    return references


def get_reference_values(es, task, subject_ids=None):
    """Get the reference values for each item in the required entities.

    Args:
        es: featuretools.EntitySet, the entity set that includes all patients' health records.
        task: Task, an object describing the prediction task and other settings.
        subject_ids: list, the indexes of the relevant cohort where the reference values are
            derived.

    Returns:
        A list including dicts of the reference values for each item in the required entity.
    """
    return {e_id: get_reference_values_by_entity(es, e_id, task.entity_configs, subject_ids)
            for e_id in task.backward_entities}


class ReferenceValue(Resource):

    def get(self, entity_id):
        """
        Get the reference values for each item in the required entity.
        ---
        tags:
          - entity set
        parameters:
          - name: entity_id
            in: path
            schema:
              type: string
            required: true
            description: ID of the entity.
        responses:
          200:
            description: The reference value of the target attributes.
            content:
              application/json:
                schema:
                  $ref: '#/components/schemas/ReferenceValues'
          400:
            $ref: '#/components/responses/ErrorMessage'
          500:
            $ref: '#/components/responses/ErrorMessage'
        """
        try:
            settings = current_app.settings
            res = get_reference_values_by_entity(settings['entityset'], entity_id,
                                                 settings['task'].entity_configs,
                                                 settings['selected_ids'])
            res = jsonify(res)
        except Exception as e:
            LOGGER.exception(e)
            return {'message': str(e)}, 500
        else:
            return res


class ReferenceValues(Resource):

    def get(self):
        """
        Get the reference values for each item in are entities used for prediction.
        ---
        tags:
          - entity set
        responses:
          200:
            description: The reference value of the target attributes.
            content:
              application/json:
                schema:
                  type: array
                  items:
                    $ref: '#/components/schemas/ReferenceValues'
          400:
            $ref: '#/components/responses/ErrorMessage'
          500:
            $ref: '#/components/responses/ErrorMessage'
        """
        try:
            settings = current_app.settings
            res = get_reference_values(settings['entityset'],
                                       settings['task'],
                                       settings['selected_ids'])
            res = jsonify(res)
        except Exception as e:
            LOGGER.exception(e)
            return {'message': str(e)}, 500
        else:
            return res
