from copy import deepcopy


def get_leaves(feature):
    if len(feature.base_features) > 0:
        return [f for feat in feature.base_features for f in get_leaves(feat)]
    else:
        return [feature]


def get_relevant_entity_id(feature):
    leave_nodes = get_leaves(feature)
    # Updated for modern featuretools 1.0+ API - use dataframe_name instead of entity_id
    entity_ids = list(set([leaf.dataframe_name for leaf in leave_nodes]))
    if len(entity_ids) > 1:
        raise UserWarning("The system do not support features constructed with data from "
                          "multiple entities. Will choose the first entity instead.")
    return entity_ids[0]


def get_relevant_column_id(feature, ignore_columns=None):
    leave_nodes = get_leaves(feature)
    # Updated for modern featuretools 1.0+ API - use column_name instead of variable.id
    column_ids = list(set([leaf.column_name for leaf in leave_nodes]))
    if ignore_columns is not None:
        column_ids = [col for col in column_ids if col not in ignore_columns]
    if len(column_ids) > 1:
        raise UserWarning("The system do not support features constructed with data from "
                          "multiple variables. Will choose the first variable instead.")
    return column_ids[0]


def get_feature_description(feature, item_dict=None, ignore_columns=None):
    if ignore_columns is None:
        ignore_columns = ['CHARTTIME', 'chartime']
    info = {
        'id': feature.get_name(),
        'primitive': feature.primitive.name,
        'entityId': get_relevant_entity_id(feature),
        'columnId': get_relevant_column_id(feature, ignore_columns=ignore_columns),
    }
    info['alias'] = info['columnId']
    info['desc'] = info['columnId']

    if 'where' in feature.__dict__:
        filter_name = feature.where.get_name()
        info['item'] = {
            'columnId': filter_name.split(' = ')[0],
            'itemId': filter_name.split(' = ')[1],
        }
        info['alias'] = feature.primitive.name
        info['desc'] = "{}({})".format(feature.primitive.name, info['item']['itemId'])
        if item_dict is not None:
            item_dict = item_dict.get(info['entityId'])
            info['item']['itemAlias'] = item_dict.get(str(info['item']['itemId']), None)
            info['desc'] = "{}({})".format(feature.primitive.name, info['item']['itemAlias'])
    return info


def group_features_by_where_item(features):
    grouped_features = deepcopy(features)
    where_item_group = {}
    for i, f in enumerate(features):
        if 'parentId' not in f and 'item' in f:
            itemId = f['item']['itemId']
            if itemId in where_item_group:
                where_item_group[itemId][0]['childrenIds'].append(i)
                grouped_features[i]['parentId'] = where_item_group[itemId][1]
            else:
                group_node = deepcopy(f)
                group_node['id'] = itemId
                group_node['primitive'] = None
                group_node['childrenIds'] = [i]
                group_node['alias'] = f['item']['itemAlias']
                grouped_features.append(group_node)
                where_item_group[itemId] = (group_node, len(grouped_features))
                grouped_features[i]['parentId'] = where_item_group[itemId][1]
    return grouped_features


def group_features_by_entity(features):
    grouped_features = deepcopy(features)
    entity_group = {}
    for i, f in enumerate(features):
        if 'parentId' in f:
            continue
        entityId = f['entityId']
        if entityId in entity_group:
            entity_group[entityId][0]['childrenIds'].append(i)
            grouped_features[i]['parentId'] = entity_group[entityId][1]
        else:
            group_node = deepcopy(f)
            group_node['id'] = entityId
            group_node['primitive'] = None
            group_node['columnId'] = None
            group_node['item'] = None
            group_node['alias'] = entityId
            group_node['childrenIds'] = [i]
            grouped_features.append(group_node)
            entity_group[entityId] = (group_node, len(grouped_features))
            grouped_features[i]['parentId'] = entity_group[entityId][1]
    return grouped_features
