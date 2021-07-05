# AUTOGENERATED! DO NOT EDIT! File to edit: 72-full-volume-processor.ipynb (unless otherwise specified).

__all__ = ['process_volume', 'flatten_volume_json']

# Cell
#dependencies

#nlp packages
import spacy
from spacy.util import minibatch, compounding

#manipulation of tables/arrays
import pandas as pd
import numpy as np
import copy
import json

#internal imports
from .collate import *
from .split_data import *
from .modeling import *
from .model_performance_utils import *
from .xml_parser import *
from .unstructured2markup import *
from .utility import *
from .relationships import *

# Cell

def process_volume(path_to_transcription, path_to_model):
    '''
    runs the transcription of a single volume (formatted according to SSDA markup 2.0 specs) through the ML entity extraction
    and rules-based relationship linking pipelines, then formats resulting data for export into SQL
        path_to_transcription: path to an XML file containing the transcription of a single volume
        path_to_model: path to a spaCy model trained to extract entities from the proper type of volume

        returns: final people, place, and event dictionaries as well as the
        path to a JSON file containing volume metadata as well as people, place, and event records
    '''

    #retrieve volume metadata and controlled vocabularies

    volume_metadata = retrieve_volume_metadata(path_to_transcription)
    images = xml_v2_to_json(path_to_transcription)
    vocabularies = retrieve_controlled_vocabularies()

    if volume_metadata["country"] == "Brazil":
        lang = "pt"
        language = "portuguese"
    else:
        lang = "es"
        language = "spanish"

    #load and apply trained model

    trained_model = load_model(path_to_model, language=lang, verbose='True')

    entry_df = parse_xml_v2(path_to_transcription)

    ent_preds_df, metrics_df, per_ent_metrics = test_model(trained_model, entry_df, "entry_no", "text", score_model=False)
    print("Entities extracted.")

    #development
    #pd.set_option("display.max_rows", 101)
    #display(ent_preds_df.head(100))

    #iterate through each entry and build relationships

    people = []
    places = []
    events = []

    entitiesRunning = pd.DataFrame()
    noCategoryRunning = pd.DataFrame()

    for i in range(len(entry_df.index)):

        entry_no = entry_df['entry_no'][i]
        entry_text = entry_df['text'][i]

        entities = ent_preds_df.loc[ent_preds_df['entry_no'] == entry_no]

        #Get the size
        entities_shape = entities.shape
        #Now define a column vector that is the approriate size, True by default
        truths_list = [True] * entities_shape[0] #[0] is the number of rows
        #Now add that column to entities
        entities.insert(0, "assgnmt_status", truths_list)

        entry_people, entry_places, entry_events, entities, characteristics_df, categorized_characteristics = build_entry_metadata(entry_text, entities, path_to_transcription, entry_no)

        #FIND ENTRIES THAT ARE UNASSIGNED OR UNCATEGORIZED
        for ent_index, ent_row in entities.iterrows():
            for char_index, char_row in characteristics_df.iterrows():
                #If CATEGORY is unassigned:
                if (char_row.loc["category"] == None) and (ent_row.loc["pred_label"] == char_row.loc["pred_label"]) and (ent_row.loc["pred_start"] == char_row.loc["pred_start"]) and (ent_row.loc["pred_entity"] == char_row.loc["pred_entity"]):
                    noCategoryRunning = noCategoryRunning.append(char_row)
                #Catergory is assigned BUT CHARACTERISTICS IS UNASSIGNED
                elif (ent_row.loc["pred_label"] == char_row.loc["pred_label"]) and (ent_row.loc["pred_start"] == char_row.loc["pred_start"]) and (ent_row.loc["pred_entity"] == char_row.loc["pred_entity"]):
                    if (char_row.loc["assignment"] == None):
                        entities.loc[ent_index,"assgnmt_status"] = False
                        characteristics_df.loc[char_index,"assgnmt_status"] = False

        entitiesRunning = entitiesRunning.append(entities)

        people += entry_people
        places += entry_places
        events += entry_events

    print("Relationships linked.")

    #disambiguate locations and assign unique ids

    unique_places = []
    for place in places:
        if (place != None) and (place not in unique_places):
            unique_places.append(place)

    for person in people:
        if (person["origin"] != None) and (person["origin"] not in unique_places):
            unique_places.append(person["origin"])

    places = []
    curr_place = 1
    for unique_place in unique_places:
        place_record = {"id":volume_metadata["id"] + '-L' + str(curr_place), "location":unique_place}
        places.append(place_record)
        curr_place += 1

    #incorporate location ids into event metadata and person records

    for event in events:
        location = event["location"]
        loc_id = "unknown"
        if location != None:
            for place in places:
                if place["location"] == location:
                    loc_id = place["id"]
        if (loc_id == "unknown") and (location != None):
            print("Failed to find location ID for " + location)
            event["location"] = None
        else:
            event["location"] = loc_id

        if event["location"] == "unknown":
            event["location"] = None

    for person in people:
        if person["origin"] == None:
            continue

        for place in places:
            if place["location"] == person["origin"]:
                person["origin"] = place["id"]
                break

    #bracket missing or incomplete event dates

    incomplete_dates = []
    last_year = None
    last_month = None
    last_day = None

    for e in range(len(events)):
        curr_year = events[e]["date"][:4]
        curr_month = events[e]["date"][5:7]
        curr_day = events[e]["date"][8:]

        #fix incompletely extracted years
        if (curr_year != "????") and (last_year != None) and (abs(int(curr_year) - int(last_year)) > 1):
            if (curr_year[3] == last_year[3]):
                curr_year = last_year
            elif (curr_month == "01") and (last_month == "12"):
                curr_year = str(int(last_year) + 1)
            else:
                curr_year = last_year
            events[e]["date"] = curr_year + '-' + curr_month + '-' + curr_day

        if (curr_year == "????") or (curr_month == "??") or (curr_day == "??"):
            #logic to assign dates for birth events based on associated baptism
            if events[e]["type"] == "birth":
                if (events[e]["id"][:events[e]["id"].find('E')] == events[e - 1]["id"][:events[e - 1]["id"].find('E')]) and (events[e - 1]["type"] == "baptism") and ('?' not in events[e - 1]["date"]):
                        if (curr_month != "??") and (curr_day != "??"):
                            if (curr_month == "12") and (last_month == "01"):
                                curr_year = str(int(last_year) - 1)
                            elif (30 * int(last_month) + int(last_day) - 30 * int(curr_month) - int(curr_day)) < 21:
                                curr_year = last_year
                            events[e]["date"] = curr_year + '-' + events[e]["date"][5:7] + '-' + events[e]["date"][8:]
                        elif curr_month != "??":
                            if (curr_month == "12"):
                                curr_day = "01"
                                curr_year = str(int(last_year) - 1)
                                events[e]["date"] = curr_year + '-' + curr_month + '-' + curr_day + '/' + last_year + '-01-01'
                            elif (curr_month == last_month):
                                curr_day = "01"
                                curr_year = last_year
                                events[e]["date"] = curr_year + '-' + curr_month + '-' + curr_day + '/' + last_year + '-' + last_month + '-' + last_day
                            elif int(curr_month) == (int(last_month) - 1):
                                curr_day = "01"
                                curr_year = last_year
                                events[e]["date"] = curr_year + '-' + curr_month + '-' + curr_day + '/' + last_year + '-' + last_month + '-01'
                        elif curr_day != "??":
                            if curr_day <= last_day:
                                curr_year = last_year
                                curr_month = last_month
                            else:
                                if last_month == "01":
                                    curr_month = "12"
                                    curr_year = str(int(last_year) - 1)
                                else:
                                    curr_month = str(int(last_month) - 1)
                                    if len(curr_month) < 2:
                                        curr_month = '0' + curr_month
                                    curr_year = last_year
                            events[e]["date"] = curr_year + '-' + curr_month + '-' + curr_day
                        else:
                            if (last_month == '01') and (int(last_day) < 21):
                                curr_year = str(int(last_year) - 1)
                                curr_month = "12"
                                curr_day = str(int(last_day) + 9)
                            elif int(last_day) < 21:
                                curr_year = last_year
                                curr_month = str(int(last_month) - 1)
                                if len(curr_month) < 2:
                                    curr_month = '0' + curr_month
                                curr_day = str(int(last_day) + 9)
                            else:
                                curr_year = last_year
                                curr_month = last_month
                                curr_day = str(int(last_day) - 20)
                                if len(curr_day) < 2:
                                    curr_day = '0' + curr_day
                            events[e]["date"] = curr_year + '-' + curr_month + '-' + curr_day + '/' + last_year + '-' + last_month + '-' + last_day

            if (curr_year == "????") or (curr_month == "??") or (curr_day == "??"):
                incomplete_dates.append(e)
        elif last_year == None:
            for date in incomplete_dates:
                events[date]["date"] = complete_date(events[date]["date"], None, curr_year + '-' + curr_month + '-' + curr_day)

            incomplete_dates = []
            last_year = curr_year
            last_month = curr_month
            last_day = curr_day
        elif (compare_dates(int(curr_year), int(curr_month), int(curr_day), int(last_year), int(last_month), int(last_day)) == '>') or (compare_dates(int(curr_year), int(curr_month), int(curr_day), int(last_year), int(last_month), int(last_day)) == '='):
            for date in incomplete_dates:
                events[date]["date"] = complete_date(events[date]["date"], last_year + '-' + last_month + '-' + last_day, curr_year + '-' + curr_month + '-' + curr_day)

            incomplete_dates = []
            last_year = curr_year
            last_month = curr_month
            last_day = curr_day

    if last_year != None:
        for date in incomplete_dates:
            events[date]["date"] = complete_date(events[date]["date"], last_year + '-' + last_month + '-' + last_day, None)

    #merging any date brackets with equal endpoints
    for event in events:
        interval = event["date"].split('/')
        if (len(interval) == 2) and (interval[0] == interval[1]):
            event["date"] == interval[0]

    print("Events configured.")

    for person in people:
        #strip titles and/or ranks from names
        if person["name"] != None:
            name_parts = person["name"].split(' ')

            if len(name_parts) >= 2:
                while ((name_parts[0].lower() + ' ' + name_parts[1].lower()) in vocabularies["titles"]) or ((name_parts[0].lower() + ' ' + name_parts[1].lower()) in vocabularies["ranks"]):
                    if len(name_parts) == 2:
                        person["name"] = None
                    else:
                        person["name"] = name_parts[2]
                        for i in range(3, len(name_parts)):
                            person["name"] += ' ' + name_parts[i]

                    if (name_parts[0].lower() + ' ' + name_parts[1].lower()) in vocabularies["titles"]:
                        if person["titles"] != None:
                            person["titles"] += ';' + name_parts[0] + ' ' + name_parts[1]
                        else:
                            person["titles"] = name_parts[0] + ' ' + name_parts[1]
                    else:
                        if person["ranks"] != None:
                            person["ranks"] += ';' + name_parts[0] + ' ' + name_parts[1]
                        else:
                            person["ranks"] = name_parts[0] + ' ' + name_parts[1]

                    if person["name"] == None:
                        break
                    name_parts = person["name"].split(' ')
                    if len(name_parts) < 2:
                        break

            if person["name"] != None:
                while (name_parts[0].lower() in vocabularies["titles"]) or (name_parts[0].lower() in vocabularies["ranks"]):
                    if len(name_parts) == 1:
                        person["name"] = None
                    else:
                        person["name"] = name_parts[1]
                        for i in range(2, len(name_parts)):
                            person["name"] += ' ' + name_parts[i]

                    if name_parts[0].lower() in vocabularies["titles"]:
                        if person["titles"] != None:
                            person["titles"] += ';' + name_parts[0]
                        else:
                            person["titles"] = name_parts[0]
                    else:
                        if person["ranks"] != None:
                            person["ranks"] += ';' + name_parts[0]
                        else:
                            person["ranks"] = name_parts[0]

                    if person["name"] == None:
                        break
                    name_parts = person["name"].split(' ')

    #normalize names and all characteristics
    names = []
    name_counts = []
    ethnonym_vocab = retrieve_json_vocab("synonyms.json", "ethnonyms")
    phenotype_vocab = retrieve_json_vocab("synonyms.json", "phenotypes", language="spanish")

    for person in people:
        #normalize characteristics and translate to English
        for key in person:
            if person[key] == None:
                continue
            if key == "name":
                person[key] = normalize_text(person[key], "synonyms.json", context="name")
                #check extracted name for ethnonyms and/or attributed phenotypes
                if (person["name"] != None) and (person["name"] != normalize_text(person["name"], "synonyms.json", context="ethnonym")):
                    for token in person["name"].split(' '):
                        eth_norm = normalize_text(token, "synonyms.json", context="ethnonym")
                        if token != eth_norm:
                            if (person["ethnicities"] == None) or (not (eth_norm in person["ethnicities"])):
                                if person["ethnicities"] == None:
                                    person["ethnicities"] = eth_norm
                                else:
                                    person["ethnicities"] = person["ethnicities"] + ';' + eth_norm
                    person["name"] = normalize_text(person["name"], "synonyms.json", context="ethnonym")
                else:
                    for ethnonym in ethnonym_vocab:
                        if ethnonym in person["name"]:
                            if person["ethnicities"] == None:
                                person["ethnicities"] = ethnonym
                            else:
                                person["ethnicities"] = person["ethnicities"] + ';' + ethnonym
                for phenotype in phenotype_vocab:
                    if phenotype in normalize_text(person[key], "synonyms.json", context="characteristic"):
                        if person["phenotype"] == None:
                            person["phenotype"] = phenotype
                        else:
                            person["phenotype"] = person["phenotype"] + ';' + phenotype
                        if phenotype[-1] == 's':
                            for token in person["name"].split(' '):
                                if normalize_text(token, "synonyms.json", context="characteristic") == phenotype:
                                    person["name"] = person["name"].replace(' ' + token, '')
            elif key == "ethnicities":
                if person[key].find(';') == -1:
                    person[key] = normalize_text(person[key], "synonyms.json", context="ethnonym")
                else:
                    char_comp = person[key].split(';')
                    person[key] = ""
                    #strip out duplicate characteristics
                    for char in char_comp:
                        char = normalize_text(char, "synonyms.json", context="ethnonym")

                        if not (char in person[key]):
                            if person[key] == "":
                                person[key] = char
                            else:
                                person[key] = person[key] + ';' + char
            elif (key != "id") and (key != "relationships"):
                if person[key].find(';') == -1:
                    person[key] = normalize_text(person[key], "synonyms.json", context="characteristic")
                    person[key] = translate_characteristic(person[key], "synonyms.json", language)
                else:
                    char_comp = person[key].split(';')
                    person[key] = ""
                    #strip out duplicate characteristics
                    for char in char_comp:
                        char = normalize_text(char, "synonyms.json", context="characteristic")
                        char = translate_characteristic(char, "synonyms.json", language)
                        if not (char in person[key]):
                            if person[key] == "":
                                person[key] = char
                            else:
                                person[key] = person[key] + ';' + char

        #future improvement: find additional references for plural characteristics

        #count name frequency
        if person["name"] != None:
            if person["name"] in names:
                name_counts[names.index(person['name'])] += 1
            else:
                names.append(person["name"])
                name_counts.append(1)

    #disambiguate and merge people across the volume
    redundant_records = []
    merged_records = []
    for i in range(len(name_counts)):
        if (name_counts[i] > .1 * len(images)) and (len(names[i].split(' ')) > 1) and (names[i] != "Unknown principal"):
            records_to_merge = []
            for j in range(len(people)):
                if people[j]["name"] == names[i]:
                    redundant_records.append(people[j])
                    records_to_merge.append(people[j])
            merged_records.append(merge_records(records_to_merge))
    people = [person for person in people if person not in redundant_records]
    for person in merged_records:
        people.append(person)

    print("People records enhanced and disambiguated.")

    #reduce compound person IDs to single ID, add references field
    people, events = compact_references(people, events)

    print("Single ID generated for each individual.")

    #convert dictionaries into JSON
    with open("volume_records\\" + volume_metadata["id"] + ".json", "w") as outfile:
        outfile.write('{\n\"volume\": \n')
        json.dump(volume_metadata, outfile)
        outfile.write(',')
        outfile.write('\n\"images\": [\n')
        first_img = True
        for image in images:
            if first_img:
                first_img = False
            else:
                outfile.write(",\n")
            json.dump(image, outfile)
        outfile.write("\n],\n")
        outfile.write('\n\"people\": [\n')
        first_person = True
        for person in people:
            if first_person:
                first_person = False
            else:
                outfile.write(",\n")
            json.dump(person, outfile)
        outfile.write("\n],\n")
        outfile.write("\"places\": [\n")
        first_place = True
        for place in places:
            if first_place:
                first_place = False
            else:
                outfile.write(",\n")
            json.dump(place, outfile)
        outfile.write("\n],\n")
        outfile.write("\"events\": [\n")
        first_event = True
        for event in events:
            if first_event:
                first_event = False
            else:
                outfile.write(",\n")
            json.dump(event, outfile)
        outfile.write("\n]\n")
        outfile.write('}')

    print("JSON built, processing completed.")

    return people, places, events, volume_metadata["id"] + "_ppe.json", entitiesRunning, noCategoryRunning

# Cell

def flatten_volume_json(path_to_volume_json, csv_root=''):
    '''
    flattens JSON record for a volume into six separate CSVs (volume, entries, people, relationships, places, and events)
        path_to_volume_json: path to a volume JSON record
        csv_root: specify directory for CSV output, including trailing /

        returns: root directory for CSVs
    '''

    with open(path_to_volume_json, encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)

    volume_id = data["volume"]["id"]

    with open(csv_root + volume_id + "_volume.csv", 'w', encoding="utf-8") as outfile:
        keys = 0
        for key in data["volume"]:
            outfile.write(key)
            keys += 1
            if keys == len(data["volume"]):
                outfile.write('\n')
            else:
                outfile.write(',')
        keys = 0
        for key in data["volume"]:
            outfile.write('"' + data["volume"][key] + '"')
            keys += 1
            if keys == len(data["volume"]):
                break
            else:
                outfile.write(',')

    with open(csv_root + volume_id + "_entries.csv", 'w', encoding="utf-8") as outfile:
        outfile.write("entry id,entry text\n")
        for image in data["images"]:
            image_id = volume_id + '-' + image["id"]
            for entry in image["entries"]:
                entry_id = image_id + '-' + str(entry["id"])
                entry_text = entry["text"]
                outfile.write(entry_id + ',' + '"' + entry_text + '"\n')

    with open(csv_root + volume_id + "_people.csv", 'w', encoding="utf-8") as outfile:
        outfile.write("id,name,origin,ethnicity,age,legitimacy,occupation,phenotype,status,titles,ranks,references\n")
        relationships = []
        for person in data["people"]:
            for key in person:
                if key == "relationships":
                    if person[key] == None:
                        continue
                    for relationship in person[key]:
                        if relationship["relationship_type"] == "godchild":
                            inverse_relationship_type = "godparent"
                        elif relationship["relationship_type"] == "godparent":
                            inverse_relationship_type = "godchild"
                        elif relationship["relationship_type"] == "grandparent":
                            inverse_relationship_type = "grandchild"
                        elif relationship["relationship_type"] == "grandchild":
                            inverse_relationship_type = "grandparent"
                        elif relationship["relationship_type"] == "parent":
                            inverse_relationship_type = "child"
                        elif relationship["relationship_type"] == "child":
                            inverse_relationship_type = "parent"
                        elif relationship["relationship_type"] == "slave":
                            inverse_relationship_type = "enslaver"
                        elif relationship["relationship_type"] == "enslaver":
                            inverse_relationship_type = "slave"
                        else:
                            inverse_relationship_type = relationship["relationship_type"]

                        inverse_relationship = {"from": relationship["related_person"], "to": person["id"], "type": inverse_relationship_type}
                        if not (inverse_relationship in relationships):
                            relationships.append({"from": person["id"], "to": relationship["related_person"], "type": relationship["relationship_type"]})

                elif key == "references":
                    references = person[key][0]
                    for index in range(1, len(person[key])):
                        references += ';' + person[key][index]
                    outfile.write(references + '\n')
                elif person[key] == None:
                    outfile.write(',')
                else:
                    outfile.write(person[key] + ',')

    with open(csv_root + volume_id + "_relationships.csv", 'w', encoding="utf-8") as outfile:
        outfile.write("from id,to id,relationship type\n")
        for relationship in relationships:
            outfile.write(relationship["from"] + ',' + relationship["to"] + ',' + relationship["type"] + '\n')

    with open(csv_root + volume_id + "_places.csv", 'w', encoding="utf-8") as outfile:
        outfile.write("id,location\n")
        for place in data["places"]:
            outfile.write(place["id"] + ',' + place["location"] + '\n')

    with open(csv_root + volume_id + "_events.csv", 'w', encoding="utf-8") as outfile:
        outfile.write("id,type,principal,date,location id,cleric\n")
        for event in data["events"]:
            for key in event:
                if event[key] == None:
                    event[key] = ''
            outfile.write(event["id"] + ',' + event["type"] + ',' + event["principal"] + ',' + event["date"] + ',' + event["location"] + ',' + event["cleric"] + '\n')

    return csv_root