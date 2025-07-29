## QTI Quiz Converter Tools 🐍
A pair of command-line Python scripts for converting QTI 1.2 quiz packages to a simple CSV format and back. This tool is designed to simplify the bulk editing of quiz questions in spreadsheet software like Excel or Google Sheets.

## Features
Export to CSV: Convert a QTI .zip package into a single, human-readable .csv file.

Import from CSV: Convert a properly formatted .csv file back into a complete QTI .zip package, ready for import into a Learning Management System (LMS) like Canvas.

Preserves Data: The conversion process handles question text, point values, multiple-choice answer options, the designated correct answer, and all feedback types (general, correct, incorrect, and per-answer).

No Dependencies: The scripts use only standard Python libraries, so no pip install is required.

## Requirements
Python 3.x

## Usage
First, download or clone this repository and navigate to the project directory in your terminal or PowerShell.

### ➡️ Converting a QTI .zip to a .csv
Use the QTIconverter.py script to unpack a QTI zip file.

Command:

Bash

python QTIconverter.py <input_quiz.zip>
Example:

Bash

python QTIconverter.py my_canvas_quiz.zip
This will create a new file named quiz_export.csv in the same directory. You can then open this CSV file to edit your questions.

### ⬅️ Converting a .csv back to a QTI .zip
After editing your questions in the CSV file, use the CSVtoQTI.py script to package it back into a QTI zip file.

Command:

Bash

python CSVtoQTI.py <input_data.csv> [output_quiz.zip]
The output file name is optional. If you don't provide one, it will default to qti_output.zip.

Example (Default Output Name):

Bash

python CSVtoQTI.py quiz_export.csv
This creates a file named qti_output.zip.

Example (Custom Output Name):

Bash

python CSVtoQTI.py quiz_export.csv final_quiz_for_import.zip
This creates a file named final_quiz_for_import.zip.

## CSV File Format
To correctly convert from CSV to QTI, your file must follow this structure.

| Column      | A                                              | B                                                  | C                                                   | D                                | E                                                                     | F                                     | G                                      | H                                     | I                                      | J                                     | K                                                       | L                                                       | M                                                         | N                                         | O                                         | P                                         | Q                                         | R                                         |
| ----------- | ---------------------------------------------- | -------------------------------------------------- | --------------------------------------------------- | -------------------------------- | --------------------------------------------------------------------- | ------------------------------------- | -------------------------------------- | ------------------------------------- | -------------------------------------- | ------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------- | ----------------------------------------- | ----------------------------------------- | ----------------------------------------- | ----------------------------------------- | ----------------------------------------- |
| Header      | Type (MC/MR)                                   | Not Used                                           | Point Value                                         | Question Body                    | Correct Answer (1-5)                                                  | Answer A                              | Answer B                               | Answer C                              | Answer D                               | Answer E                              | General Comments                                        | Correct Answer Comment                                  | Wrong Answer Comment                                      | Feedback for A                            | Feedback for B                            | Feedback for C                            | Feedback for D                            | Feedback for E                            |
| Description | The question type. Use MC for multiple choice. | This column must be present but can be left blank. | The point value of the question (e.g., 5.0 or 1.5). | The text of the question itself. | The number corresponding to the correct answer (1=A, 2=B, 3=C, etc.). | The text for the first answer choice. | The text for the second answer choice. | The text for the third answer choice. | The text for the fourth answer choice. | The text for the fifth answer choice. | General feedback shown to all students after answering. | Feedback shown only to students who answered correctly. | Feedback shown only to students who answered incorrectly. | Specific feedback for selecting answer A. | Specific feedback for selecting answer B. | Specific feedback for selecting answer C. | Specific feedback for selecting answer D. | Specific feedback for selecting answer E. |
