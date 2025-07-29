import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile
import sys
import uuid
import os
import re

def create_qti_zip_from_csv(csv_path, zip_path='qti_export.zip', quiz_title=None):
    """
    Reads a CSV file and generates a QTI 1.2 compliant zip file.

    Args:
        csv_path (str): The path to the input CSV file.
        zip_path (str): The path for the output QTI zip file.
        quiz_title (str, optional): The title for the quiz. Defaults to the CSV filename.
    """
    if not quiz_title:
        quiz_title = os.path.splitext(os.path.basename(csv_path))[0]

    # Generate unique identifiers for the quiz components
    assessment_ident = f"i{uuid.uuid4().hex}"
    dependency_ident = f"i{uuid.uuid4().hex}"
    resource_ident = f"i{uuid.uuid4().hex}"
    manifest_ident = f"i{uuid.uuid4().hex}"
    
    # --- 1. Build the main QTI XML content ---
    qti_root = ET.Element("questestinterop", {
        "xmlns": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2 http://www.imsglobal.org/xsd/ims_qtiasiv1p2p1.xsd"
    })
    assessment = ET.SubElement(qti_root, "assessment", {"ident": assessment_ident, "title": quiz_title})
    section = ET.SubElement(assessment, "section", {"ident": "root_section"})

    total_points = 0.0

    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader) # Skip header row

        for i, row in enumerate(reader):
            # Map CSV columns to variables
            q_type, _, q_points, q_body, correct_ans_idx, *answers_and_feedback = row
            q_points = float(q_points) if q_points else 0.0
            total_points += q_points
            
            answers = answers_and_feedback[0:5]
            feedbacks = {
                'general': answers_and_feedback[5],
                'correct': answers_and_feedback[6],
                'incorrect': answers_and_feedback[7],
                'individual': answers_and_feedback[8:13]
            }

            item_ident = f"i{uuid.uuid4().hex}"
            item = ET.SubElement(section, "item", {"ident": item_ident, "title": f"Question {i+1}"})

            # --- Item Metadata (Question Type, Points) ---
            itemmetadata = ET.SubElement(item, "itemmetadata")
            qtimetadata = ET.SubElement(itemmetadata, "qtimetadata")
            
            # Question Type
            qtimetadatafield_type = ET.SubElement(qtimetadata, "qtimetadatafield")
            ET.SubElement(qtimetadatafield_type, "fieldlabel").text = "question_type"
            ET.SubElement(qtimetadatafield_type, "fieldentry").text = "multiple_choice_question" if q_type == "MC" else "multiple_response_question"

            # Points Possible
            qtimetadatafield_points = ET.SubElement(qtimetadata, "qtimetadatafield")
            ET.SubElement(qtimetadatafield_points, "fieldlabel").text = "points_possible"
            ET.SubElement(qtimetadatafield_points, "fieldentry").text = str(q_points)

            # --- Presentation (Question and Answers) ---
            presentation = ET.SubElement(item, "presentation")
            material = ET.SubElement(presentation, "material")
            ET.SubElement(material, "mattext", {"texttype": "text/html"}).text = f"<div><p>{q_body}</p></div>"
            
            response_lid = ET.SubElement(presentation, "response_lid", {"ident": "response1", "rcardinality": "Single"})
            render_choice = ET.SubElement(response_lid, "render_choice")

            answer_ids = []
            for ans_text in answers:
                if ans_text: # Only add non-empty answers
                    ans_ident = f"i{uuid.uuid4().hex}"
                    answer_ids.append(ans_ident)
                    response_label = ET.SubElement(render_choice, "response_label", {"ident": ans_ident})
                    ans_material = ET.SubElement(response_label, "material")
                    ET.SubElement(ans_material, "mattext", {"texttype": "text/plain"}).text = ans_text
            
            # --- Resprocessing (Scoring Logic) ---
            resprocessing = ET.SubElement(item, "resprocessing")
            ET.SubElement(resprocessing, "outcomes").append(ET.Element("decvar", {"maxvalue": "100", "minvalue": "0", "varname": "SCORE", "vartype": "Decimal"}))
            
            # Correct answer condition
            correct_answer_id = answer_ids[int(correct_ans_idx) - 1]
            respcondition = ET.SubElement(resprocessing, "respcondition", {"continue": "No"})
            conditionvar = ET.SubElement(respcondition, "conditionvar")
            ET.SubElement(conditionvar, "varequal", {"respident": "response1"}).text = correct_answer_id
            ET.SubElement(respcondition, "setvar", {"action": "Set", "varname": "SCORE"}).text = "100"

            # --- Feedback ---
            if feedbacks['general']:
                fb_general = ET.SubElement(item, "itemfeedback", {"ident": "general_fb"})
                ET.SubElement(ET.SubElement(fb_general, "flow_mat"), "material").append(ET.Element("mattext", {"texttype": "text/html"}, text=f"<p>{feedbacks['general']}</p>"))
            if feedbacks['correct']:
                fb_correct = ET.SubElement(item, "itemfeedback", {"ident": "correct_fb"})
                ET.SubElement(ET.SubElement(fb_correct, "flow_mat"), "material").append(ET.Element("mattext", {"texttype": "text/html"}, text=f"<p>{feedbacks['correct']}</p>"))
            if feedbacks['incorrect']:
                fb_incorrect = ET.SubElement(item, "itemfeedback", {"ident": "general_incorrect_fb"})
                ET.SubElement(ET.SubElement(fb_incorrect, "flow_mat"), "material").append(ET.Element("mattext", {"texttype": "text/html"}, text=f"<p>{feedbacks['incorrect']}</p>"))

            for j, fb_text in enumerate(feedbacks['individual']):
                if fb_text:
                    fb_ind = ET.SubElement(item, "itemfeedback", {"ident": f"{answer_ids[j]}_fb"})
                    ET.SubElement(ET.SubElement(fb_ind, "flow_mat"), "material").append(ET.Element("mattext", {"texttype": "text/html"}, text=f"<p>{fb_text}</p>"))

    # --- 2. Build the imsmanifest.xml file ---
    manifest_root = ET.Element("manifest", {
        "identifier": manifest_ident,
        "xmlns": "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1",
        "xmlns:lom": "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource",
        "xmlns:imsmd": "http://www.imsglobal.org/xsd/imsmd_v1p2",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1 http://www.imsglobal.org/xsd/imscp_v1p1.xsd"
    })
    resources = ET.SubElement(manifest_root, "resources")
    resource_qti = ET.SubElement(resources, "resource", {"identifier": resource_ident, "type": "imsqti_xmlv1p2"})
    ET.SubElement(resource_qti, "file", {"href": f"{assessment_ident}/{assessment_ident}.xml"})
    ET.SubElement(resource_qti, "dependency", {"identifierref": dependency_ident})
    resource_meta = ET.SubElement(resources, "resource", {"identifier": dependency_ident, "type": "associatedcontent/imscc_xmlv1p1/learning-application-resource", "href": f"{assessment_ident}/assessment_meta.xml"})
    ET.SubElement(resource_meta, "file", {"href": f"{assessment_ident}/assessment_meta.xml"})

    # --- 3. Build the assessment_meta.xml file ---
    meta_root = ET.Element("quiz", {
        "identifier": assessment_ident,
        "xmlns": "http://canvas.instructure.com/xsd/cccv1p0",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": "http://canvas.instructure.com/xsd/cccv1p0 https://canvas.instructure.com/xsd/cccv1p0.xsd"
    })
    ET.SubElement(meta_root, "title").text = quiz_title
    ET.SubElement(meta_root, "points_possible").text = str(total_points)
    ET.SubElement(meta_root, "quiz_type").text = "assignment"

    # --- 4. Prettify and write XML files ---
    def prettify(elem):
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    qti_xml_str = prettify(qti_root)
    manifest_xml_str = prettify(manifest_root)
    meta_xml_str = prettify(meta_root)

    # --- 5. Create the zip archive ---
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("imsmanifest.xml", manifest_xml_str)
        zf.writestr(f"{assessment_ident}/{assessment_ident}.xml", qti_xml_str)
        zf.writestr(f"{assessment_ident}/assessment_meta.xml", meta_xml_str)
    
    print(f"Successfully created QTI zip file at: {zip_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_file_path = sys.argv[1]
        zip_file_name = "qti_output.zip"
        if len(sys.argv) > 2:
            zip_file_name = sys.argv[2]
        # --- THIS LINE IS NOW FIXED ---
        create_qti_zip_from_csv(csv_file_path, zip_file_name)
    else:
        print("Usage: python CSVtoQTI.py <path_to_csv_file> [output_zip_name]")