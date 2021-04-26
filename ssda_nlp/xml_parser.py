# AUTOGENERATED! DO NOT EDIT! File to edit: 12-ssda-xml-parser.ipynb (unless otherwise specified).

__all__ = ['parse_xml', 'parse_xml_v2', 'xml_v2_to_json', 'retrieve_volume_metadata']

# Cell
import pandas as pd

# Cell
def parse_xml(file_name):
    master_xml = open(file_name,"r",encoding='utf-8')
    vol_titls = []
    vol_ids = []
    entry_txts = []
    entry_ids = []
    fol_ids = []
    curr_vol_titl = ""
    curr_vol_id= ""
    curr_fol_id = ""
    curr_entry = ""

    in_entry = False

    for line in master_xml:
        if (line.find('<') != -1) and (line.find('<', line.find('<') + 1) != -1):
            line_content = line[line.find('>') + 1:line.find('<', line.find('<') + 1)]
        elif line[len(line) - 2] == '-':
            line_content = line[:len(line) - 2]
        else:
            line_content = line[:len(line) - 1] + ' '

        if "<volumeTitle>" in line:
            curr_vol_titl = line_content
            #set current volume title
        elif "<volumeIdentifier>" in line:
            curr_vol_id = line_content
        #set current volume identifier
        elif "<itemIdentifier>" in line:
            entry_id = 0
            curr_fol_id = line_content
        #set current folio id
        elif "<entry>" in line:
            entry_id += 1
            in_entry = True
            curr_entry = ""
        #toggle in entry flag
        elif in_entry and (not "</entry>" in line):
            curr_entry += line_content
        #add line to current entry
        elif in_entry and ("</entry>" in line):
            in_entry = False
        #toggle entry flag, append all current variables to lists
            vol_titls.append(curr_vol_titl)
            vol_ids.append(curr_vol_id)
            fol_ids.append(curr_fol_id)
            entry_txts.append(curr_entry)
            entry_ids.append(curr_fol_id + '-' + str(entry_id))

    columns = {'vol_titl':vol_titls, 'vol_id':vol_ids, 'fol_id':fol_ids, 'text':entry_txts, 'entry_no':entry_ids}

    df = pd.DataFrame(columns)
    master_xml.close()
    return df

# Cell

def parse_xml_v2(path_to_xml):
    master_xml = open(path_to_xml,"r",encoding='utf-8')
    vol_titls = []
    vol_ids = []
    entry_txts = []
    entry_ids = []
    fol_ids = []
    curr_vol_titl = ""
    curr_vol_id= ""
    curr_fol_id = ""
    curr_entry = ""

    in_entry = False
    in_partial_entry = False

    for line in master_xml:
        if "<volume" in line:
            title_start = line.find('\"', line.find("title=")) + 1
            title_end = line.find('\"', title_start)
            curr_vol_titl = line[title_start:title_end]
            id_start = line.find('\"', line.find("id=")) + 1
            id_end = line.find('\"', id_start)
            curr_vol_id = line[id_start:id_end]
        elif "<image" in line:
            entry_id = 0
            id_start = line.find('\"', line.find("id=")) + 1
            id_end = line.find('\"', id_start)
            curr_fol_id = line[id_start:id_end]
        elif ("<entry" in line) and in_partial_entry:
            in_partial_entry = False
            vol_titls.append(curr_vol_titl)
            vol_ids.append(curr_vol_id)
            fol_ids.append(str(int(curr_fol_id) - 1))
            entry_txts.append(curr_entry)
            entry_ids.append(str(int(curr_fol_id) - 1) + '-' + str(partial_id))
            curr_entry = ''
            in_entry = True
            entry_id += 1
        elif "<entry" in line:
            entry_id += 1
            in_entry = True
            curr_entry = ""
        elif "<partial id" in line:
            in_partial_entry = True
            entry_id += 1
            partial_id = entry_id
            curr_entry = ''
        elif in_partial_entry and ("image" in line) or ("partial" in line):
            continue
        elif in_entry and ("</entry>" in line):
            in_entry = False
            vol_titls.append(curr_vol_titl)
            vol_ids.append(curr_vol_id)
            fol_ids.append(curr_fol_id)
            entry_txts.append(curr_entry)
            entry_ids.append(curr_fol_id + '-' + str(entry_id))
        elif in_entry or in_partial_entry:
            while line[0] == ' ':
                line = line[1:]
            if ((line[len(line) - 1] == '\n') or (line[len(line) - 1] == '\n')) and (line[len(line) - 2] == '-'):
                curr_entry += line[:len(line) - 2]
            elif line[len(line) - 1] == '-':
                curr_entry += line[:len(line) - 1]
            elif (line == '\n') or (line == '\n'):
                continue
            elif (line[len(line) - 1] == '\n') or (line[len(line) - 1] == '\n'):
                curr_entry += line[:len(line) - 1] + ' '
            else:
                while line[len(line) - 1] == ' ':
                    line = line[:-1]
                curr_entry += line

    columns = {'vol_titl':vol_titls, 'vol_id':vol_ids, 'fol_id':fol_ids, 'text':entry_txts, 'entry_no':entry_ids}

    df = pd.DataFrame(columns)
    master_xml.close()
    return df

# Cell

def xml_v2_to_json(path_to_xml):
    master_xml = open(path_to_xml,"r",encoding='utf-8')
    vol_titls = []
    vol_ids = []
    entry_txts = []
    entry_ids = []
    img_ids = []
    img_types = []
    img_num = []
    curr_vol_titl = ""
    curr_vol_id= ""
    curr_img_id = ""
    curr_entry = ""
    curr_img_type = ""
    curr_img_num = ""

    in_entry = False
    in_partial_entry = False

    images = []
    curr_img_dict = None

    for line in master_xml:
        if "<volume" in line:
            title_start = line.find('\"', line.find("title=")) + 1
            title_end = line.find('\"', title_start)
            curr_vol_titl = line[title_start:title_end]
            id_start = line.find('\"', line.find("id=")) + 1
            id_end = line.find('\"', id_start)
            curr_vol_id = line[id_start:id_end]
        elif "<image" in line:
            if curr_img_dict != None:
                images.append(curr_img_dict)
            entry_id = 0
            id_start = line.find('\"', line.find("id=")) + 1
            id_end = line.find('\"', id_start)
            curr_img_id = line[id_start:id_end]
            type_start = line.find('\"', line.find("type=")) + 1
            type_end = line.find('\"', type_start)
            curr_img_type = line[type_start:type_end]
            if line.find("number=") == -1:
                curr_img_num = None
            else:
                num_start = line.find('\"', line.find("number=")) + 1
                num_end = line.find('\"', num_start)
                curr_img_num = line[num_start:num_end]
            curr_img_dict = {"id": curr_img_id, "type": curr_img_type, "number": curr_img_num, "entries": []}
        elif ("<entry" in line) and in_partial_entry:
            in_partial_entry = False
            vol_titls.append(curr_vol_titl)
            vol_ids.append(curr_vol_id)
            img_ids.append(str(int(curr_img_id) - 1))
            entry_txts.append(curr_entry)
            entry_ids.append(str(int(curr_img_id) - 1) + '-' + str(partial_id))
            curr_img_dict["entries"].append({"id": entry_id, "text": curr_entry})
            curr_entry = ''
            in_entry = True
            entry_id += 1
        elif "<entry" in line:
            entry_id += 1
            in_entry = True
            curr_entry = ""
        elif "<partial id" in line:
            in_partial_entry = True
            entry_id += 1
            partial_id = entry_id
            curr_entry = ''
        elif in_partial_entry and ("image" in line) or ("partial" in line):
            continue
        elif in_entry and ("</entry>" in line):
            in_entry = False
            vol_titls.append(curr_vol_titl)
            vol_ids.append(curr_vol_id)
            img_ids.append(curr_img_id)
            entry_txts.append(curr_entry)
            entry_ids.append(curr_img_id + '-' + str(entry_id))
            curr_img_dict["entries"].append({"id": entry_id, "text": curr_entry})
        elif in_entry or in_partial_entry:
            while line[0] == ' ':
                line = line[1:]
            if ((line[len(line) - 1] == '\n') or (line[len(line) - 1] == '\n')) and (line[len(line) - 2] == '-'):
                curr_entry += line[:len(line) - 2]
            elif line[len(line) - 1] == '-':
                curr_entry += line[:len(line) - 1]
            elif (line == '\n') or (line == '\n'):
                continue
            elif (line[len(line) - 1] == '\n') or (line[len(line) - 1] == '\n'):
                curr_entry += line[:len(line) - 1] + ' '
            else:
                while line[len(line) - 1] == ' ':
                    line = line[:-1]
                curr_entry += line
        elif "</ssda" in line:
            images.append(curr_img_dict)

    master_xml.close()
    return images

# Cell

def retrieve_volume_metadata(path_to_xml):
    xml = open(path_to_xml,"r",encoding='utf-8')
    volume_metadata = {}
    metadata_fields = ["type", "country", "state", "city", "institution", "id", "title"]

    for line in xml:
        if "<volume" in line:
            for field in metadata_fields:
                volume_metadata[field] = line[line.find('=', line.find(field)) + 2:line.find('\"', line.find('=', line.find(field)) + 2)]

    return volume_metadata