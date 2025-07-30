import csv
import xml.etree.ElementTree as ET
import re
import zipfile
import sys
import os

def clean_html(raw_html):
    """
    Removes HTML tags from a string.
    """
    if not raw_html:
        return ""
    clean_text = re.sub('<[^<]+?>', '', raw_html)
    return clean_text.strip()

def convert_qti_to_csv(zip_file_path, output_dir='csv_output'):
    """
    Parses a QTI zip file and converts each quiz into a separate CSV file.

    Args:
        zip_file_path (str): The file path to the QTI zip file.
        output_dir (str): The directory where the output CSV files will be saved.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with zipfile.ZipFile(zip_file_path, 'r') as z:
            manifest_xml = z.read('imsmanifest.xml')
            manifest_root = ET.fromstring(manifest_xml)
            
            ns_map = {
                'imscp': 'http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1',
                'ims': 'http://www.imsglobal.org/xsd/ims_qtiasiv1p2'
            }

            resources = manifest_root.findall('.//imscp:resource[@type="imsqti_xmlv1p2"]', ns_map)

            if not resources:
                print("Error: No QTI XML resources found in the manifest.")
                return

            for resource in resources:
                qti_xml_filename = resource.find('imscp:file', ns_map).get('href')
                
                # Extract quiz title from assessment_meta.xml
                dependency_id = resource.find('imscp:dependency', ns_map).get('identifierref')
                meta_resource = manifest_root.find(f'.//imscp:resource[@identifier="{dependency_id}"]', ns_map)
                meta_xml_filename = meta_resource.get('href')
                
                with z.open(meta_xml_filename) as meta_xml_file:
                    meta_tree = ET.parse(meta_xml_file)
                    quiz_title = meta_tree.find('.//{http://canvas.instructure.com/xsd/cccv1p0}title').text
                    sanitized_title = re.sub(r'[^\w\s-]', '', quiz_title).strip().replace(' ', '_')
                    output_csv_path = os.path.join(output_dir, f"{sanitized_title}.csv")


                with z.open(qti_xml_filename) as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

                    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csv_file:
                        writer = csv.writer(csv_file)
                        header = [
                            'Type (MC/MR)', 'Not Used', 'Point Value', 'Question Body',
                            'Correct Answer (1-5)', 'Answer A', 'Answer B', 'Answer C', 
                            'Answer D', 'Answer E', 'General Comments', 
                            'Correct Answer Comment', 'Wrong Answer Comment',
                            'Feedback for A', 'Feedback for B', 'Feedback for C',
                            'Feedback for D', 'Feedback for E'
                        ]
                        writer.writerow(header)

                        for item in root.findall('.//ims:item', ns_map):
                            csv_row = [""] * 18
                            
                            for field in item.findall('.//ims:qtimetadatafield', ns_map):
                                label_elem = field.find('ims:fieldlabel', ns_map)
                                if label_elem is not None:
                                    if label_elem.text == 'question_type':
                                        q_type_elem = field.find('ims:fieldentry', ns_map)
                                        if q_type_elem is not None and q_type_elem.text == 'multiple_choice_question':
                                            csv_row[0] = 'MC'
                                    elif label_elem.text == 'points_possible':
                                        points_elem = field.find('ims:fieldentry', ns_map)
                                        if points_elem is not None and points_elem.text:
                                            points = float(points_elem.text)
                                            csv_row[2] = f"{points:.2f}"

                            question_body_elem = item.find('.//ims:presentation//ims:mattext', ns_map)
                            if question_body_elem is not None:
                                csv_row[3] = clean_html(question_body_elem.text)
                            
                            answers, answer_ids = [], []
                            for i, label in enumerate(item.findall('.//ims:render_choice/ims:response_label', ns_map)):
                                answer_text_elem = label.find('.//ims:mattext', ns_map)
                                answer_text = clean_html(answer_text_elem.text) if answer_text_elem is not None else ""
                                answer_id = label.get('ident')
                                answers.append(answer_text)
                                answer_ids.append(answer_id)
                                if i < 5:
                                    csv_row[5 + i] = answer_text

                            correct_answer_id = None
                            for condition in item.findall('.//ims:respcondition', ns_map):
                                setvar = condition.find('.//ims:setvar[@varname="SCORE"]', ns_map)
                                if setvar is not None and setvar.text == '100' and setvar.get('action') == 'Set':
                                    varequal = condition.find('.//ims:varequal', ns_map)
                                    if varequal is not None:
                                        correct_answer_id = varequal.text
                                        break 

                            if correct_answer_id and correct_answer_id in answer_ids:
                               correct_answer_index = answer_ids.index(correct_answer_id)
                               csv_row[4] = str(correct_answer_index + 1)

                            feedback_map = {}
                            for fb in item.findall('.//ims:itemfeedback', ns_map):
                                ident = fb.get('ident')
                                fb_text_elem = fb.find('.//ims:mattext', ns_map)
                                feedback_text = clean_html(fb_text_elem.text) if fb_text_elem is not None else ""
                                feedback_map[ident] = feedback_text
                            
                            csv_row[10] = feedback_map.get('general_fb', '')
                            csv_row[11] = feedback_map.get('correct_fb', '')
                            csv_row[12] = feedback_map.get('general_incorrect_fb', '')
                            
                            for i, ans_id in enumerate(answer_ids):
                                if i < 5:
                                    feedback_key = f"{ans_id}_fb"
                                    if feedback_key in feedback_map:
                                        csv_row[13 + i] = feedback_map[feedback_key]

                            writer.writerow(csv_row)
                    print(f"Successfully created CSV file at: {output_csv_path}")

    except FileNotFoundError:
        print(f"Error: The file '{zip_file_path}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        zip_file_path = sys.argv[1]
        convert_qti_to_csv(zip_file_path)
    else:
        print("Error: Please provide the path to the zip file.")
        print("Usage: python QTIconverter.py <path_to_zip_file>")