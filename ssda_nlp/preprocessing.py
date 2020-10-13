# AUTOGENERATED! DO NOT EDIT! File to edit: 51-data-preprocessing.ipynb (unless otherwise specified).

__all__ = ['xml_to_jsonl', 'parse_annotation', 'prodigy_output_to_collated_df']

# Cell

import srsly
from .xml_parser import *
import pandas as pd

# Cell

def xml_to_jsonl(path_to_xml_transcription):
    xml_transcription = open(path_to_xml_transcription, 'r', encoding="utf-8")
    prodigy_input = open(path_to_xml_transcription[:path_to_xml_transcription.find(".xml")] + ".jsonl", 'w', encoding="utf-8")

    in_entry = False
    current_entry = ''

    for line in xml_transcription:
        if "<entry" in line:
            in_entry = True
        elif in_entry and ("</entry>" in line):
            current_entry += line[:line.find("</entry>")]
            in_entry = False
            prodigy_input.write("{\"text\":\"" + current_entry + "\"}\n")
            current_entry = ''
        elif in_entry:
            while line[0] == ' ':
                line = line[1:]
            if ((line[len(line) - 1] == '\n') or (line[len(line) - 1] == '\r')) and (line[len(line) - 2] == '-'):
                current_entry += line[:len(line) - 2]
            elif line[len(line) - 1] == '-':
                current_entry += line[:len(line) - 1]
            elif (line == '\n') or (line == '\r'):
                continue
            elif (line[len(line) - 1] == '\n') or (line[len(line) - 1] == '\r'):
                current_entry += line[:len(line) - 1] + ' '
            else:
                while line[len(line) - 1] == ' ':
                    line = line[:-1]
                current_entry += line

    xml_transcription.close()
    prodigy_input.close()

    return

# Cell

def parse_annotation(path_to_annotation):
    annotation = srsly.read_jsonl(path_to_annotation)

    spans = []
    texts = []

    for entry in annotation:
        texts.append(entry["text"])
        temp = []
        if "spans" in entry:
            for span in entry["spans"]:
                temp.append([span["start"], span["end"], span["label"]])
        spans.append(temp)

    #build list of unique entries and list of empty annotation dictionaries for each
    annot_ls = []

    for text in texts:
        annot_ls.append({"entities":[]})

    #populate annotation dictionaries
    for i in range(len(texts)):
        for span in spans[i]:
            annot_ls[i]["entities"].append((int(span[0]), int(span[1]), span[2]))

    #build list of tuples
    tuples = []
    for i in range(len(texts)):
        tuples.append((texts[i], annot_ls[i]))

    return tuples

# Cell

def prodigy_output_to_collated_df(path_to_annotation):
    tuples = parse_annotation(path_to_annotation)
    entry_nos = []
    entry_texts = []
    entities = []
    starts = []
    ends = []
    labels = []
    entry = 1
    for tup in tuples:
        for entity in tup[1]["entities"]:
            entry_nos.append(entry)
            entry_texts.append(tup[0])
            entities.append(tup[0][entity[0]:entity[1]])
            starts.append(entity[0])
            ends.append(entity[1])
            labels.append(entity[2])
        entry += 1

    collated_dict = {"entry_no": entry_nos, "text": entry_texts, "entity": entities, "start": starts, "end": ends, "label": labels}

    collated_df = pd.DataFrame(collated_dict)

    return collated_df