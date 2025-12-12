import csv
import xml.etree.ElementTree as ET
import re
import zipfile
import argparse
import html
import sys
import traceback

def clean_text(raw_text):
    """Removes HTML tags and unescapes entities (e.g. &amp; -> &)."""
    if not raw_text:
        return ""
    # Strip HTML tags
    clean = re.sub('<[^<]+?>', '', raw_text)
    # Fix entities (e.g. &nbsp;, &gt;)
    return html.unescape(clean).strip()

def convert_qti_to_csv(zip_file_path, output_csv_path):
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as z:
            # Filter for likely QTI files (excluding manifest/meta)
            qti_files = [f for f in z.namelist() if f.endswith('.xml') 
                         and 'imsmanifest' not in f and 'assessment_meta' not in f]
            
            if not qti_files:
                print("Error: QTI XML file not found in the zip archive.")
                return

            with z.open(qti_files[0]) as xml_file:
                try:
                    tree = ET.parse(xml_file)
                except ET.ParseError as e:
                    print(f"Error: Could not parse XML file. {e}")
                    return
                    
                ns = {'ims': 'http://www.imsglobal.org/xsd/ims_qtiasiv1p2'}
                root = tree.getroot()

                fieldnames = [
                    'Type', 'Title', 'Points', 'Question Body',
                    'Correct Answer', 'Option 1', 'Option 2', 'Option 3', 
                    'Option 4', 'Option 5', 'General Feedback', 
                    'Correct Feedback', 'Incorrect Feedback',
                    'Feedback 1', 'Feedback 2', 'Feedback 3',
                    'Feedback 4', 'Feedback 5'
                ]

                # FIX: Use 'utf-8-sig' to add the BOM for Excel compatibility
                with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as csv_file:
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                    writer.writeheader()

                    count = 0
                    skipped_count = 0

                    for item in root.findall('.//ims:item', ns):
                        row = {key: "" for key in fieldnames}
                        
                        # --- 1. Validation: Check Question Type ---
                        is_supported_type = False
                        q_type_metadata = ""
                        
                        for field in item.findall('.//ims:qtimetadatafield', ns):
                            label = field.find('ims:fieldlabel', ns)
                            entry = field.find('ims:fieldentry', ns)
                            
                            if label is not None and label.text == 'question_type':
                                q_type_metadata = entry.text if entry is not None else ""
                            
                            # Also grab points while we are looping through metadata
                            if label is not None and label.text == 'points_possible':
                                raw_points = entry.text if entry is not None else "0"
                                try:
                                    row['Points'] = f"{float(raw_points):.2f}"
                                except ValueError:
                                    row['Points'] = "0.00"

                        # Allow MC, True/False, or if metadata is missing
                        if q_type_metadata in ['multiple_choice_question', 'true_false_question', 'multiple_response_question', '']:
                            is_supported_type = True
                        
                        if not is_supported_type:
                            print(f"Skipping unsupported question type: {q_type_metadata} (Item Title: {item.get('title')})")
                            skipped_count += 1
                            continue

                        # --- 2. Extract Basic Data ---
                        row['Title'] = item.get('title', 'Question')
                        
                        mattext = item.find('.//ims:presentation//ims:mattext', ns)
                        if mattext is not None:
                            row['Question Body'] = clean_text(mattext.text)

                        # --- 3. Extract Answers ---
                        labels = item.findall('.//ims:render_choice/ims:response_label', ns)
                        answer_ids = []
                        answer_texts = []
                        
                        for i, label in enumerate(labels):
                            if i >= 5: break
                            text_elem = label.find('.//ims:mattext', ns)
                            text = clean_text(text_elem.text) if text_elem is not None else ""
                            
                            row[f'Option {i+1}'] = text
                            answer_ids.append(label.get('ident'))
                            answer_texts.append(text)

                        # --- 4. Robust Type Detection ---
                        # Check for True/False regardless of case (True, TRUE, true)
                        lower_answers = [a.lower() for a in answer_texts]
                        if len(answer_texts) == 2 and "true" in lower_answers and "false" in lower_answers:
                            row['Type'] = "TF"
                        else:
                            row['Type'] = "MC"

                        # --- 5. Correct Answer ---
                        correct_id = None
                        for cond in item.findall('.//ims:respcondition', ns):
                            # Safety check: ensure setvar exists
                            setvar = cond.find(".//ims:setvar[@action='Set']", ns)
                            if setvar is not None and setvar.text == '100':
                                varequal = cond.find(".//ims:varequal", ns)
                                if varequal is not None:
                                    correct_id = varequal.text
                                    break
                        
                        if correct_id in answer_ids:
                            row['Correct Answer'] = str(answer_ids.index(correct_id) + 1)

                        # --- 6. Feedback ---
                        feedbacks = {}
                        for fb in item.findall('.//ims:itemfeedback', ns):
                            ident = fb.get('ident')
                            txt = fb.find('.//ims:mattext', ns)
                            feedbacks[ident] = clean_text(txt.text) if txt is not None else ""

                        row['General Feedback'] = feedbacks.get('general_fb', '')
                        row['Correct Feedback'] = feedbacks.get('correct_fb', '')
                        row['Incorrect Feedback'] = feedbacks.get('general_incorrect_fb', '')

                        for i, aid in enumerate(answer_ids):
                            key = f"{aid}_fb"
                            if key in feedbacks:
                                row[f'Feedback {i+1}'] = feedbacks[key]

                        writer.writerow(row)
                        count += 1
                        
                print(f"Success! Extracted {count} questions to: {output_csv_path}")
                if skipped_count > 0:
                    print(f"Warning: {skipped_count} items were skipped because they were not Multiple Choice or True/False.")

    except FileNotFoundError:
        print(f"Error: The file '{zip_file_path}' was not found.")
    except zipfile.BadZipFile:
        print(f"Error: The file '{zip_file_path}' is not a valid zip archive.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert QTI Zip to CSV")
    parser.add_argument("input", help="Path to QTI zip file")
    parser.add_argument("output", nargs='?', default="quiz_export.csv", help="Output CSV path")
    args = parser.parse_args()
    
    convert_qti_to_csv(args.input, args.output)