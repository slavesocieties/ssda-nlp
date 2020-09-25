# AUTOGENERATED! DO NOT EDIT! File to edit: 52-unstructured-to-markup.ipynb (unless otherwise specified).

__all__ = ['universal_markup_converter']

# Cell

def universal_markup_converter(path_to_transcription, transcription_type):

    if transcription_type == "markup v1":
        inp = open(path_to_transcription,'r',encoding="utf-8")
        transcription = ''
        for line in inp:
            transcription += line
        typ = input("Enter record type: ")
        country = input("Enter country: ")
        state = input("Enter first-level administrative division: ")
        city = input("Enter city: ")
        institution = input("Enter institution: ")
        output_dir = input("Enter output directory: ")
        vol_id_loc = transcription.find("<volumeIdentifier>")
        volume_identifier = transcription[vol_id_loc + len("<volumeIdentifier>"):transcription.find('<',vol_id_loc + 1)]
        vol_titl_loc = transcription.find("<volumeTitle>")
        volume_title = transcription[vol_titl_loc + len("<volumeTitle>"):transcription.find('<',vol_titl_loc + 1)]
        img_type = input("Enter image file extensions: ")
        curr_image_id = int(input("Enter first transcribed image file name: "))
        inp.close()
        inp = open(path_to_transcription,'r',encoding="utf-8")

        output = open(output_dir,'w',encoding="utf-8")
        output.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
        output.write("<ssda xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\">\n")
        output.write("<volume type=\"" + typ + "\" country=\"" + country + "\" state=\"" + state + "\" city=\"" + city + "\" institution=\"" + institution + "\" id=\"" + volume_identifier + "\" title=\"" + volume_title + "\">\n")

        in_entry = False
        for line in inp:
            if "<itemTitle>" in line:
                folio_start = line.find(' ')
                curr_image_number = line[folio_start + 1:line.find('.', folio_start)]
                output.write("<image id=\"" + str(curr_image_id) + "\" type=\"" + img_type + "\" number=\"" + curr_image_number + "\">\n")
                curr_image_id += 1
                curr_entry = 1
            elif "<entry>" in line:
                in_entry = True
                output.write("<entry id=\"" + str(curr_entry) + "\">\n")
                curr_entry += 1
            elif "</entry>" in line:
                in_entry = False
                output.write("</entry>\n")
            elif in_entry:
                output.write(line)
            elif "</item>" in line:
                output.write("</image>\n")

        output.write("</volume>\n")
        output.write("</ssda>")

        inp.close()
        output.close()
    else:
        print("that transcription type is not supported yet")

    return