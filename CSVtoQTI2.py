import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile
import uuid
import os
import argparse
import sys

def create_qti_zip(csv_path, zip_path):
    quiz_title = os.path.splitext(os.path.basename(csv_path))[0]
    
    # Generate unique IDs for the package
    assessment_id = f"i{uuid.uuid4().hex}"
    manifest_id = f"i{uuid.uuid4().hex}"
    dependency_id = f"i{uuid.uuid4().hex}"

    # Setup XML root
    qti_root = ET.Element("questestinterop", {
        "xmlns": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2 http://www.imsglobal.org/xsd/ims_qtiasiv1p2p1.xsd"
    })
    assessment = ET.SubElement(qti_root, "assessment", {"ident": assessment_id, "title": quiz_title})
    section = ET.SubElement(assessment, "section", {"ident": "root_section"})

    total_points = 0.0
    warnings = []
    question_count = 0

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Normalize headers (strip spaces)
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            for i, row in enumerate(reader):
                row_num = i + 2 # Account for header and 0-index
                
                # --- 1. Basic Data Extraction ---
                q_type = row.get('Type', 'MC').upper().strip()
                title = row.get('Title', f'Question {i+1}')
                body = row.get('Question Body', '')
                
                # --- 2. Validation: Points ---
                try:
                    points = float(row.get('Points', 0))
                except ValueError:
                    warnings.append(f"Row {row_num}: Invalid points value '{row.get('Points')}'. Defaulting to 0.")
                    points = 0.0
                total_points += points

                # --- 3. Construct Options ---
                answers = []
                if q_type == 'TF':
                    answers = ["True", "False"]
                elif q_type == 'MC':
                    for x in range(1, 6):
                        val = row.get(f'Option {x}', '').strip()
                        if val: answers.append(val)
                    
                    if not answers:
                        warnings.append(f"Row {row_num}: Question '{title}' has no answer options detected.")
                else:
                    warnings.append(f"Row {row_num}: Unknown Type '{q_type}'. Defaulting to MC.")
                    
                # --- 4. Validation: Correct Answer ---
                raw_correct = row.get('Correct Answer', '').strip()
                correct_idx = -1
                
                if raw_correct.isdigit():
                    correct_idx = int(raw_correct) - 1 # Convert to 0-index
                else:
                    warnings.append(f"Row {row_num}: Missing or non-numeric Correct Answer. Question will have no correct answer.")

                if correct_idx != -1:
                    if correct_idx < 0 or correct_idx >= len(answers):
                        warnings.append(f"Row {row_num}: Correct Answer '{raw_correct}' is out of range (1-{len(answers)}).")
                        correct_idx = -1 # Invalidate

                # --- 5. Build XML Item ---
                item = ET.SubElement(section, "item", {"ident": f"i{uuid.uuid4().hex}", "title": title})
                question_count += 1
                
                # Metadata
                meta = ET.SubElement(ET.SubElement(item, "itemmetadata"), "qtimetadata")
                
                # Type Field
                f_type = ET.SubElement(meta, "qtimetadatafield")
                ET.SubElement(f_type, "fieldlabel").text = "question_type"
                q_type_str = "true_false_question" if q_type == 'TF' else "multiple_choice_question"
                ET.SubElement(f_type, "fieldentry").text = q_type_str

                # Points Field
                f_points = ET.SubElement(meta, "qtimetadatafield")
                ET.SubElement(f_points, "fieldlabel").text = "points_possible"
                ET.SubElement(f_points, "fieldentry").text = str(points)

                # Presentation
                pres = ET.SubElement(item, "presentation")
                mat = ET.SubElement(pres, "material")
                ET.SubElement(mat, "mattext", {"texttype": "text/html"}).text = f"<div><p>{body}</p></div>"

                lid = ET.SubElement(pres, "response_lid", {"ident": "response1", "rcardinality": "Single"})
                render = ET.SubElement(lid, "render_choice")

                # Generate IDs for answers
                answer_ids = []
                for ans_text in answers:
                    a_id = f"i{uuid.uuid4().hex}"
                    answer_ids.append(a_id)
                    label = ET.SubElement(render, "response_label", {"ident": a_id})
                    ET.SubElement(ET.SubElement(label, "material"), "mattext", {"texttype": "text/plain"}).text = ans_text

                # Processing (Scoring)
                res = ET.SubElement(item, "resprocessing")
                ET.SubElement(res, "outcomes").append(ET.Element("decvar", {"maxvalue": "100", "minvalue": "0", "varname": "SCORE", "vartype": "Decimal"}))
                
                if correct_idx != -1:
                    correct_id = answer_ids[correct_idx]
                    cond = ET.SubElement(res, "respcondition", {"continue": "No"})
                    ET.SubElement(ET.SubElement(cond, "conditionvar"), "varequal", {"respident": "response1"}).text = correct_id
                    ET.SubElement(cond, "setvar", {"action": "Set", "varname": "SCORE"}).text = "100"

                # Feedback Handling
                def add_feedback(ident, text):
                    if text:
                        fb = ET.SubElement(item, "itemfeedback", {"ident": ident})
                        ET.SubElement(ET.SubElement(fb, "flow_mat"), "material").append(
                            ET.Element("mattext", {"texttype": "text/html"}, text=f"<p>{text}</p>")
                        )

                add_feedback("general_fb", row.get('General Feedback'))
                add_feedback("correct_fb", row.get('Correct Feedback'))
                add_feedback("general_incorrect_fb", row.get('Incorrect Feedback'))
                
                # Per-answer feedback (Only for MC usually, but code handles TF cleanly too)
                if q_type != 'TF': 
                    for x in range(1, 6):
                        if x-1 < len(answer_ids):
                            add_feedback(f"{answer_ids[x-1]}_fb", row.get(f'Feedback {x}'))

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to read CSV. {e}")
        return

    # --- Print Warnings ---
    if warnings:
        print("\n⚠️  VALIDATION WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        print("\nProceeding with export, but please check the quiz in Canvas/LMS after import.\n")
    else:
        print("\n✅  Validation passed: No errors found in CSV.")

    # --- Write Files (Manifest, Meta, Zip) ---
    manifest = ET.Element("manifest", {
        "identifier": manifest_id,
        "xmlns": "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1",
        "xmlns:imsmd": "http://www.imsglobal.org/xsd/imsmd_v1p2"
    })
    resources = ET.SubElement(manifest, "resources")
    
    # QTI Resource
    res_qti = ET.SubElement(resources, "resource", {"identifier": f"res_{assessment_id}", "type": "imsqti_xmlv1p2"})
    ET.SubElement(res_qti, "file", {"href": f"{assessment_id}/{assessment_id}.xml"})
    ET.SubElement(res_qti, "dependency", {"identifierref": dependency_id})
    
    # Meta Resource
    res_meta = ET.SubElement(resources, "resource", {"identifier": dependency_id, "type": "associatedcontent/imscc_xmlv1p1/learning-application-resource", "href": f"{assessment_id}/assessment_meta.xml"})
    ET.SubElement(res_meta, "file", {"href": f"{assessment_id}/assessment_meta.xml"})

    # Meta XML
    meta_root = ET.Element("quiz", {
        "xmlns": "http://canvas.instructure.com/xsd/cccv1p0",
        "identifier": assessment_id
    })
    ET.SubElement(meta_root, "title").text = quiz_title
    ET.SubElement(meta_root, "points_possible").text = str(total_points)
    ET.SubElement(meta_root, "quiz_type").text = "assignment"

    # Prettify helper
    def prettify(elem):
        rough = ET.tostring(elem, 'utf-8')
        return minidom.parseString(rough).toprettyxml(indent="  ")

    try:
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("imsmanifest.xml", prettify(manifest))
            zf.writestr(f"{assessment_id}/{assessment_id}.xml", prettify(qti_root))
            zf.writestr(f"{assessment_id}/assessment_meta.xml", prettify(meta_root))
        
        print(f"Successfully created QTI zip: {zip_path}")
        print(f"Total Questions: {question_count}")
        print(f"Total Points: {total_points}")

    except Exception as e:
        print(f"Error writing zip file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert CSV to QTI Zip")
    parser.add_argument("input", help="Path to input CSV")
    parser.add_argument("output", nargs='?', default="qti_import.zip", help="Output Zip path")
    args = parser.parse_args()
    
    create_qti_zip(args.input, args.output)