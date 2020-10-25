# AUTOGENERATED! DO NOT EDIT! File to edit: 71-relationship-builder.ipynb (unless otherwise specified).

__all__ = ['assign_characteristics', 'assign_relationships', 'id_unique_individuals', 'find_sus', 'split_name_col',
           'disambiguate', 'determine_principals', 'determine_event_date', 'determine_event_location',
           'identify_cleric', 'build_event', 'drop_obvious_duplicates', 'assign_unique_ids', 'build_entry_metadata']

# Cell
#dependencies

#nlp packages
import spacy
from spacy.util import minibatch, compounding

#manipulation of tables/arrays
import pandas as pd
import numpy as np
import copy

#internal imports
from .collate import *
from .split_data import *
from .modeling import *
from .model_performance_utils import *
from .xml_parser import *
from .unstructured2markup import *

# Cell

def assign_characteristics(entry_text, entities, unique_individuals):
    '''
    matches all labeled characteristics to the correct individual(s) and builds triples
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        unique_individuals: as determined by id_unique_individuals and/or meta-function of disambig pipeline

        returns: structured representation (a list of dictionaries)
    '''
    people = []

    for i in range(len(unique_individuals[0])):
        people.append({"id": unique_individuals[1][i], "name": unique_individuals[0][i]})

    return people

# Cell

def assign_relationships(entry_text, entities, unique_individuals):
    '''
    Relationship types:
        parent/child
        godparents/godchildren
        slaveholders/enslaved
        spouses
        grandparents

    Identify typical relationship words/phrases:
    1. eslava --> slave --> typically appears as NAME1 esclava de NAME2

    Process
    1. Manually check entry_text for substrings such as "eslava de"
        '''
    pass
    #print(entry_text)
    #print(unique_individuals)
    #print("------------")

# Cell

def id_unique_individuals(entry_text, entities, volume_metadata):
    '''
    identifies all unique individuals that appear in an entry (i.e. removing all multiple mentions of the same person)
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        volume_metadata: metadata for the volume that the entry comes from, built by retrieve_volume_metadata

        returns: a list of the unique individuals who appear in an entry AND (temporary?) unique IDs for each individual
    '''
    event_id = volume_metadata["id"] + '-' + entities.iloc[0]['entry_no']

    people_df = entities.loc[entities['pred_label'] == 'PER']
    people_df.reset_index(inplace=True)
    people_df = people_df.drop('index',axis=1)
    unique_individuals = people_df['pred_entity'].unique()
    unique_individuals = np.vstack([unique_individuals, [None] * len(unique_individuals)])

    for i in range(len(unique_individuals[0])):
        unique_individuals[1][i] = event_id + '-P' + str(i + 1)

    return unique_individuals

# Cell

def find_sus(entry_text, entities, sus_df, index):
    '''
    identifies corner cases: all entries where there are multiple entities that 1) have the same first name appearing
        multiple times, 2) have compound names and then a segment of that name appearing, and 3) have a full name with
        the first name by itself appearing
    Note that this should not be used in tandem with id_unique_individuals, as that function just drops the duplicate names

    params:
        entry_text: actual text for comparison
        entities: df of entities identified
        sus_df: either the empty df body or the df from previously loop iterations
        i: current row that the loop is on in DEMO_DF

    returns: df of all the entries that may be corner cases, in the same form demo_df, but with two added id columns
    '''
    #Set up
    people_df = entities.loc[entities['pred_label'] == 'PER']
    people_df.reset_index(inplace=True)
    people_df = people_df.drop('index',axis=1)

    my_rows = len(people_df.index)
    hold = my_rows * [0]
    people_df['name_status'] = hold
    first_names = []
    check_against = []
    dups = 0
    sus = 0

    #Get a list of all the first names that appear in the entities/people_df
    #  This is definitely not the most computationally efficient way to do this
    for i in range(my_rows):
        #Separate people based on whether it is a first name or a full/compound name
        if (" " in people_df.iloc[i,1]) or ("-" in people_df.iloc[i,1]):
            check_against.append(people_df.iloc[i,1])
        elif ~(" " in people_df.iloc[i,1]): #No spaces thus we are assuming it is a first name
            first_names.append(people_df.iloc[i,1])
    #Check to see whether they are subsets of full/compound names
    if len(first_names)>0 and len(check_against)>0:
        for j in range(len(first_names)):
            for k in range(len(check_against)):
                if first_names[j] in check_against[k]:
                    #Mark this entire entry as sus
                    sus = 1
    #Generally check to see if there are any duplicate entities (same name) in the entry
    if people_df['pred_entity'].duplicated().any():
        dups = 1;
    #Set the status column
    if sus and dups:
        status = 11 #ie both sus and dups are true
    elif sus:
        status = 10 #ie sus true, dups false
    elif dups:
        status = 0.01 #ie sus false, dups true
    else:
        status = 0
    #ie if the entry is suspect or has duplicates, then add it to sus_df
    if status>0:
        if len(sus_df.index)<1:
            data = [{'vol_titl':demo_df.iloc[index,0], 'vol_id':demo_df.iloc[index,1], 'fol_id':demo_df.iloc[index,2],
                    'text':demo_df.iloc[index,3],'entry_no':entry_no,'suspect':status}]
            sus_df = pd.DataFrame(data)
        else:
            sus_df = sus_df.append({'vol_titl':demo_df.iloc[index,0], 'vol_id':demo_df.iloc[index,1], 'fol_id':demo_df.iloc[index,2],
                    'text':demo_df.iloc[index,3],'entry_no':entry_no,'suspect':status},ignore_index=True)
    return sus_df

# Cell

def split_name_col(people_df):
    '''
    from the fed in entities, strips DF to only include people, then separates based on if it is a first name or a full name


    ### Functionality is not fully realized yet, could probably be generalized further, but this entire task may not be necessary
    '''
    #Set up
    my_rows = len(people_df.index)
    hold = my_rows * [0]
    people_df['name_status'] = hold

    #Separate into two based on first/single and full name status
    for i in range(my_rows):
        if "-" in people_df.iloc[i,1]:
            people_df.iloc[i,5] = 2 #2 therefore represents compound name
        elif " " in people_df.iloc[i,1]:
            people_df.iloc[i,5] = 1 #1 therefore represents a full name
        else: #Must be a single name
            #0 therefore represents a full name
            pass
    first_n = people_df[people_df.name_status == 0]
    full_n = people_df[people_df.name_status == 1]
    cmpd_n = people_df[people_df.name_status == 2]

    print("DF of first names")
    display(first_n.head())
    print("DF of full names")
    display(full_n.head())
    print("DF of compound names")
    display(cmpd_n.head())
    print("---------------------")

    return first_n, full_n, cmpd_n

# Cell

def disambiguate():
    '''
    goes through the problem cases previously identified and then applies split_name_col to break the entities down into
        the ones that may be
    '''
    people_df = entities.loc[entities['pred_label'] == 'PER']
    people_df.reset_index(inplace=True)
    people_df = people_df.drop('index',axis=1)

    first_n, full_n, cmpd_n = split_name_col(people_df)


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
    principals = []

    if n_principals == 1:

        for index, entity in entities.iterrows():
            if entity['pred_label'] == 'PER' and entity['pred_start'] <= 20:
                principals.append(entity['pred_entity'])

        if len(principals) == 0:
            prox = entry_text.find('oleos')
            if prox != -1:
                for index, entity in entities.iterrows():
                    if entity['pred_label'] == 'PER' and (abs(entity['pred_start'] - prox) <= 10):
                        principals.append(entity['pred_entity'])

        if len(principals) == 0:
            prox = entry_text.find('nombre')
            if prox != -1:
                for index, entity in entities.iterrows():
                    if entity['pred_label'] == 'PER' and (abs(entity['pred_start'] - prox) <= 10):
                        principals.append(entity['pred_entity'])

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
            if (entity['pred_label'] == 'DATE') and (entity['pred_entity'] != primary_event_date):
                date = entity['pred_entity']

    elif volume_metadata["type"] == "baptism":
        entry_length = len(entry_text)

        for index, entity in entities.iterrows():
            if (entity['pred_label'] == 'DATE') and (entity['pred_start'] <= (entry_length / 3)):
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

def build_event(entry_text, entities, event_type, principals, volume_metadata, n_event_within_entry):
    '''
    builds out relationships related to a baptism or burial event
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        event_type: this could be either a valid record_type OR a secondary event like a birth
        principals: the principal(s) of the event, as indicated by determine_principals
        volume_metadata: metadata for the volume that the entry comes from, built by retrieve_volume_metadata

        n_event_within_entry: event number within entry

        returns: structured representation of these relationships, including (but not necessarily limited to)
        the event's principal, the date of the event, the location of the event, and the associated cleric
    '''
    event_id = volume_metadata["id"] + '-' + entities.iloc[0]['entry_no'] + '-E' + str(n_event_within_entry)
    #it's possible that this function should also be returning an event iterator,
    #but for now I'm planning to do that in build_relationships

    if event_type == "baptism":
        if len(principals) == 0:
            principal = None
        else:
            principal = principals[0]
        date = determine_event_date(entry_text, entities, event_type, volume_metadata)
        location = determine_event_location(entry_text, entities, event_type, volume_metadata)
        cleric = identify_cleric(entry_text, entities)
    else:
        print("That event type can't be built yet.")
        return

    event_relationships = {"id": event_id, "type": event_type, "principal": principal, "date": date, "location": location, "cleric": cleric}

    return event_relationships

# Cell

def drop_obvious_duplicates(people, principals, cleric):
    '''
    first-pass disambiguation that drops multiple mentions of cleric and principal(s)
        people: df containing all entities labeled as people in the entry
        principals: as indicated by determine_principals

        returns: people df with obvious duplicates dropped
    '''
    found_principal = False
    found_cleric = False
    indices_to_drop = []

    if len(principals) == 1:
        for index, person in people.iterrows():
            if (person['pred_entity'] == principals[0]) and (found_principal == False):
                found_principal = True
            elif person['pred_entity'] == principals[0]:
                people.drop(index, inplace=True)

            if cleric != None:
                if (person['pred_entity'] == cleric) and (found_cleric == False):
                    found_cleric = True
                elif person['pred_entity'] == cleric:
                    people.drop(index, inplace=True)

    people.reset_index(inplace=True)

    return people

# Cell

def assign_unique_ids(people, volume_metadata):
    '''
    assigns unique ids to each person in an entry
        people: df containing all entities labeled as people in the entry that has received first-pass disambiguation
        volume_metadata: metadata for the volume that the entry comes from, built by retrieve_volume_metadata

        returns: people df with column containing unique ids appended
    '''
    size = len(people.index)
    unique_ids = []
    entry_id = volume_metadata["id"] + '-' + people.iloc[0]['entry_no']

    for i in range(size):
        unique_ids.append(entry_id + '-P' + str(i+1))

    people['unique_id'] = unique_ids

    return people

# Cell

def build_entry_metadata(entry_text, entities, path_to_volume_xml):
    '''
    Master function that will combine all helper functions built above
        entry_text: the full text of a single entry, ported directly from spaCy to ensure congruity
        entities: entities of all kinds extracted from that entry by an NER model
        path_to_volume_xml: path to xml file containing full volume transcription and volume-level metadata

        returns: paths to three JSON files containg, respectively,
        metadata re people, places, and events that appear in the entry
    '''

    volume_metadata = retrieve_metadata(path_to_volume_xml)
    people_df = copy.deepcopy(entities.loc[entities['pred_label'] == 'PER'])
    people_df.reset_index(inplace=True)

    if volume_metadata["type"] == "baptism":
        principal = determine_principals(entry_text, entities, 1)
        cleric = identify_cleric(entry_text, entities)
        people_df = assign_unique_ids(drop_obvious_duplicates(people_df, principal, cleric), volume_metadata)
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