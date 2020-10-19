# AUTOGENERATED! DO NOT EDIT! File to edit: 71-relationship-builder.ipynb (unless otherwise specified).

__all__ = ['id_unique_individuals', 'determine_principals', 'determine_event_date', 'determine_event_location',
           'identify_cleric', 'build_event', 'build_relationships']

# Cell

def id_unique_individuals(entry_text, entities, record_type):
    '''
    identifies all unique individuals that appear in an entry (i.e. removing all multiple mentions of the same person)
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        record_type: simple flag indicating whether records are baptisms, marriages, burials, etc. (this can also be determined
        programmatically and may be deprecated later)

        returns: a list of the unique individuals who appear in an entry
    '''
    people_df = entities.loc[entities['pred_label'] == 'PER']
    people_df.reset_index(inplace=True)
    people_df = people_df.drop('index',axis=1)
    unique_individuals = people_df['pred_entity'].unique()

    return unique_individuals

# Cell

def determine_principals(entry_text, entities, n_principals):
    '''
    determines the principal of a single-principal event
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        n_principals: expected number of principals

        returns: the principal(s) of the event in question, or None if no principal can be identified
    '''

    entry_text = entry_text.lower()

    if n_principals == 1:
        principals = None

        for index, entity in entities.iterrows():
            if entity['pred_label'] == 'PER' and entity['pred_start'] <= 20:
                principals = entity['pred_entity']

        if principals == None:
            prox = entry_text.find('oleos')
            if prox != -1:
                for index, entity in entities.iterrows():
                    if entity['pred_label'] == 'PER' and (abs(entity['pred_start'] - prox) <= 10):
                        principals = entity['pred_entity']

        if principals == None:
            prox = entry_text.find('nombre')
            if prox != -1:
                for index, entity in entities.iterrows():
                    if entity['pred_label'] == 'PER' and (abs(entity['pred_start'] - prox) <= 10):
                        principals = entity['pred_entity']

    elif n_principals == 2:
        print("That number of principals is not supported yet.")
        return None
        #process marriage principals
    else:
        print("Invalid number of principals.")
        return None

    return principals

# Cell

def determine_event_date(entry_text, entities, event_type, volume_metadata):
    '''
    determines the date of a specific event
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        event_type: this could be either a valid record_type OR a secondary event like a birth
        volume_metadata: metadata for the volume that the entry comes from, built by retrieve_volume_metadata

        returns: the date of the event in question, or None if no date can be identified
    '''
    date = None

    if event_type != volume_metadata["type"]:
        primary_event_date = determine_event_date(entry_text, entities, event_type, volume_metadata)
        for index, entity in entities.iterrows():
            if entity['pred_label'] == 'DATE' and entity['pred_entity'] != primary_event_date:
                date = entity['pred_entity']

    elif volume_metadata["type"] == "baptism":
        entry_length = len(entry_text)

        for index, entity in entities.iterrows():
            if entity['pred_label'] == 'DATE' and entity['pred_start'] <= (entry_length / 3):
                date = entity['pred_entity']

    else:
        date = "That event type is not supported yet."

    return date

# Cell

def determine_event_location(entry_text, entities, event_type, volume_metadata):
    '''
    determines the location of a specific event
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        event_type: this could be either a valid record_type OR a secondary event like a birth
        volume_metadata: metadata for the volume that the entry comes from, built by retrieve_volume_metadata

        returns: the location of the event in question, or None if no date can be identified
    '''
    location = None

    if event_type == volume_metadata["type"]:
        location = volume_metadata["institution"]
    else:
        location = "That event type is not supported yet."

    return location

# Cell

def identify_cleric(entry_text, entities):
    '''
    identifies the cleric(s) associated with a sacramental entry
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model

        returns: the associated cleric(s), or None if no date can be identified
    '''
    clerics = None

    for index, entity in entities.iterrows():
            if ((entity['pred_label'] == 'PER') and ((len(entry_text) - entity['pred_end']) <= 10) and (len(entry_text) > 100)):
                clerics = entity['pred_entity']
            #going to keep this condition for now, but it can create false positives when long, incorrect entities are extracted
            #from short and/or garbled entries
            elif (entity['pred_entity'] != None) and (len(entry_text) - entity['pred_end'] <= 2) and (entity['pred_label'] == 'PER'):
                clerics = entity['pred_entity']

    if clerics == None:
        pvs_label = None
        pvs_end = None
        for index, entity in entities.iterrows():
            if entity['pred_label'] == 'PER' and pvs_label == 'DATE' and (entity['pred_start'] - pvs_end) <= 15:
                clerics = entity['pred_entity']
            pvs_label = entity['pred_label']
            pvs_end = entity['pred_end']

    if clerics == None:
        entry_text = entry_text.lower()
        for index, entity in entities.iterrows():
            if entity['pred_label'] == 'PER' and entry_text.find("cura", entity['pred_start'] + len(entity['pred_entity'])) != -1 and ((entry_text.find("cura", entity['pred_start'] + len(entity['pred_entity']))) - entity['pred_end']) <= 15:
                clerics = entity['pred_entity']

    return clerics

# Cell

def build_event(entry_text, entities, event_type, principals):
    '''
    builds out relationships related to a baptism or burial event
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model

        returns: structured representation of these relationships, including (but not necessarily limited to)
        the event's principal, the date of the event, the location of the event, and the associated cleric
    '''

    date = determine_event_date(entry_text, entities, event_type)
    location = determine_event_location(entry_text, entities, event_type)
    cleric = identify_cleric(entry_text, entities)

    return event_relationships

# Cell

def build_relationships(entry_text, entities, path_to_volume_xml):
    '''
    Master function that will combine all helper functions built above
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        record_type: simple flag indicating whether records are baptisms, marriages, burials, etc. (this can also be determined
        programmatically and may be deprecated later)

        returns: structured data (specific format to be named later) containing all relationships extracted
    '''
    #unique_individuals = id_unique_indviduals(entry_text, entities, record_type)

    volume_metadata = retrieve_metadata(path_to_volume_xml)

    if volume_metadata["type"] == "baptism":
        principals = determine_principals(entry_text, entities, 1)
        #event_relationships = build_event(entry_text, entities, "baptism", principals)
        #interpersonal_relationships = process_interpersonal(entry_text, entities)
        #characteristics = process_characteristics(entry_text, entities, interpersonal_relationships)
    elif volume_metadata["type"] == "marriage":
        #process marriage record
        print("That record type is not supported yet.")
        return None
    elif volume_metadata["type"] == "burial":
        #process burial record
        print("That record type is not supported yet.")
        return None
    else:
        print("That record type is not supported yet.")
        return None

    #code that turns pieces defined above into well-formed relationships

    return relationships