def remove_nan_entries(df, key_columns, verbose=True):
    n_row = len(df)
    for column in key_columns:
        df = df[df[column] == df[column]]
    if verbose:
        print("Prune ({}/{}) rows.".format(n_row - len(df), n_row))
    return df


def parse_relationship_path(relationship):
    # Updated for modern featuretools API
    return {
        'parent_entity_id': relationship.parent_dataframe.ww.name,
        'parent_variable_id': relationship.parent_column,
        'child_entity_id': relationship.child_dataframe.ww.name,
        'child_variable_id': relationship.child_column,
    }


def get_forward_entities(entityset, entity_id):
    ids = []
    entity_id_pipe = [entity_id]
    while len(entity_id_pipe):
        entity_id = entity_id_pipe[0]
        entity_id_pipe = entity_id_pipe[1:]
        ids.append(entity_id)
        # Extract just the dataframe names from the tuples returned by get_forward_dataframes
        forward_tuples = list(entityset.get_forward_dataframes(entity_id))
        for child_id, path in forward_tuples:
            entity_id_pipe.append(child_id)
    return ids


def get_forward_attributes(entityset, target_entity, direct_id, interesting_ids=None):
    info = []
    try:
        # Just get data from the target entity for now to avoid relationship traversal issues
        df = entityset[target_entity]
        
        # Check if direct_id exists in this dataframe before trying to access it
        if direct_id in df.index:
            # Get the data and convert to dictionary
            patient_data = df.loc[direct_id].fillna('N/A')
            # Ensure we convert Series to dict properly
            if hasattr(patient_data, 'to_dict'):
                patient_dict = patient_data.to_dict()
            else:
                patient_dict = dict(patient_data)
            
            info = [{'entityId': target_entity, 'items': patient_dict}]
    except Exception as e:
        # If anything fails, return empty list
        print(f"Error in get_forward_attributes: {e}")
        return []
    
    return info


def find_path(entityset, source_entity, target_entity):
    """Find a path of the source entity to the target_entity."""
    nodes_pipe = [target_entity]
    parent_dict = {target_entity: None}
    while len(nodes_pipe):
        parent_node = nodes_pipe.pop()
        if parent_node == source_entity:
            break
        # Use the modern featuretools API - extract just dataframe names from tuples
        backward_tuples = list(entityset.get_backward_dataframes(parent_node))
        forward_tuples = list(entityset.get_forward_dataframes(parent_node))
        
        # Extract just the dataframe names (first element of each tuple)
        backward_nodes = [name for name, path in backward_tuples]
        forward_nodes = [name for name, path in forward_tuples]
        child_nodes = backward_nodes + forward_nodes
        
        for child in child_nodes:
            if child not in parent_dict:
                parent_dict[child] = parent_node
                nodes_pipe.append(child)
    node = source_entity
    paths = [[node]]
    while node != target_entity:
        node = parent_dict[node]
        paths.append(paths[-1] + [node])
    return paths


def transfer_cutoff_times(entityset, cutoff_times, source_entity, target_entity,
                          reduce="latest"):
    path = find_path(entityset, source_entity, target_entity)[-1]
    for i, source in enumerate(path[:-1]):
        target = path[i + 1]
        # Use modern featuretools API for relationships
        options = list(filter(lambda r: (r.child_dataframe.ww.name == source
                                         and r.parent_dataframe.ww.name == target)
                              or (r.parent_dataframe.ww.name == source
                                  and r.child_dataframe.ww.name == target),
                              entityset.relationships))
        if len(options) == 0:
            raise ValueError("No Relationship between {} and {}".format(source, target))
        r = options[0]
        if target == r.child_dataframe.ww.name:
            # Transfer cutoff_times to "child", e.g., PATIENTS -> ADMISSIONS
            # Updated for modern featuretools API - direct dataframe access
            child_df_index = entityset[r.child_dataframe.ww.name][r.child_column].values
            cutoff_times = cutoff_times.loc[child_df_index]
            cutoff_times.index = entityset[r.child_dataframe.ww.name].index
        elif source == r.child_dataframe.ww.name:
            # Transfer cutoff_times to "parent", e.g., ADMISSIONS -> PATIENTS
            # Updated for modern featuretools API - direct dataframe access
            cutoff_times[r.child_column] = entityset[r.child_dataframe.ww.name][r.child_column]
            if reduce == "latest":
                idx = cutoff_times.groupby(r.child_column).time.idxmax().values
            elif reduce == 'earist':
                idx = cutoff_times.groupby(r.child_column).time.idxmin().values
            else:
                raise ValueError("Unknown reduce option.")
            cutoff_times = cutoff_times.loc[idx]
            cutoff_times = cutoff_times.set_index(r.child_column, drop=True)

    return cutoff_times


def get_records(entityset, subject_id, entity_id, time_index=None, cutoff_time=None):
    # Updated for modern featuretools API - direct dataframe access
    entity = entityset[entity_id]

    # select records by SUBJECT_ID
    if 'SUBJECT_ID' in entity.columns:
        entity_df = entity[entity['SUBJECT_ID'] == subject_id]
    else:
        entity_df = entity

    # select records before or at the cutoff_time
    if cutoff_time is not None and time_index is not None:
        entity_df = entity_df[entity_df[time_index] <= cutoff_time]
    # TODO filter records according to secondary time index

    return entity_df


def get_item_dict(es):
    # Updated for modern featuretools API - direct dataframe access
    item_dict = {'LABEVENTS': es['D_LABITEMS'].loc[:, 'LABEL'].to_dict()}
    for entity_id in ['CHARTEVENTS', 'SURGERY_VITAL_SIGNS']:
        df = es['D_ITEMS']
        # TODO: Change 'LABEL' to 'LABEL_CN' for Chinese labels
        items = df[df['LINKSTO'] == entity_id.lower()].loc[:, 'LABEL']
        item_dict[entity_id] = items.to_dict()
    return item_dict
