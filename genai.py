import streamlit as st
import pandas as pd
import re
import time
import os
from groq import Groq
from groq import RateLimitError


# ================================
# PAGE CONFIG
# ================================

st.set_page_config(
    page_title="Gen AI Quality Issue Analyzer",
    layout="wide"
)

st.title(" Generative AI–Based Manufacturing Quality Issue Analyzer")
st.write("Upload manufacturing defect data or enter a defect manually to generate engineering improvement recommendations.")


# ================================
# API INITIALIZATION
# ================================

GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)


# ================================
# FUNCTIONS
# ================================

def format_issue(row):

    return f"""
Defect Type: {row['defect_type']}
Location: {row['defect_location']}
Severity: {row['severity']}
Inspection Method: {row['inspection_method']}
Repair Cost: {row['repair_cost']}
"""


def build_prompt(issue_text):

    return f"""
You are a manufacturing engineering assistant.

Provide structured engineering improvement recommendations 
based strictly on the issue information below.

Do NOT perform root cause analysis.
Do NOT provide explanations outside required format.
Provide only practical engineering improvements.

Issue Information:
{issue_text}

Output Format (Follow Exactly):

1. Issue Category:
2. Engineering Solutions:
3. Implementation Priority:
4. Operational Impact:
"""


def assign_priority(severity):

    severity = str(severity).strip().lower()

    if severity == "critical":
        return "High"
    elif severity == "moderate":
        return "Medium"
    elif severity == "minor":
        return "Low"
    else:
        return "Unknown"


def extract_structured_fields_from_text(user_input):

    extraction_prompt = f"""
Extract the following fields from the text below.

Required Output Format:
Defect Type:
Defect Location:
Severity:
Inspection Method:

Text:
{user_input}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": extraction_prompt}],
        temperature=0
    )

    return response.choices[0].message.content


def parse_extracted_fields(extracted_text):

    defect_type = re.search(r"Defect Type:\s*(.*)", extracted_text)
    defect_location = re.search(r"Defect Location:\s*(.*)", extracted_text)
    severity = re.search(r"Severity:\s*(.*)", extracted_text)
    inspection_method = re.search(r"Inspection Method:\s*(.*)", extracted_text)

    return {
        "defect_type": defect_type.group(1).strip() if defect_type else "Unknown",
        "defect_location": defect_location.group(1).strip() if defect_location else "Unknown",
        "severity": severity.group(1).strip() if severity else "Unknown",
        "inspection_method": inspection_method.group(1).strip() if inspection_method else "Unknown",
        "repair_cost": "Unknown"
    }


def extract_issue_and_solutions(text):

    issue_match = re.search(r"Issue Category:\s*(.*)", text)
    issue_category = issue_match.group(1).strip() if issue_match else "Not Found"

    solutions_match = re.search(
        r"Engineering Solutions:(.*?)(Implementation Priority:)",
        text,
        re.DOTALL
    )

    engineering_solutions = (
        solutions_match.group(1).strip()
        if solutions_match else "Not Found"
    )

    # remove trailing numbering like "3."
    engineering_solutions = re.sub(r"\n?\s*\d+\.\s*$", "", engineering_solutions)

    return issue_category, engineering_solutions


# ================================
# MODE SELECTION
# ================================

mode = st.sidebar.radio(
    "Select Input Mode",
    ["CSV Upload", "Manual Input"]
)


# ================================
# CSV MODE
# ================================

if mode == "CSV Upload":

    uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

    if uploaded_file:

        df = pd.read_csv(uploaded_file)

        st.success("Dataset Loaded")

        st.dataframe(df.head())

        total_rows = len(df)

        start = st.number_input("Start Row", min_value=1, max_value=total_rows, value=1)
        end = st.number_input("End Row", min_value=1, max_value=total_rows, value=min(5, total_rows))

        if st.button("Analyze Dataset"):

            results = []
            progress = st.progress(0)

            for idx in range(start - 1, end):

                row = df.iloc[idx]

                issue_text = format_issue(row)
                prompt = build_prompt(issue_text)

                while True:
                    try:
                        response = client.chat.completions.create(
                            model="llama-3.1-8b-instant",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.2
                        )
                        break

                    except RateLimitError:
                        st.warning("Rate limit reached. Waiting 10 seconds...")
                        time.sleep(10)

                llm_output = response.choices[0].message.content

                true_priority = assign_priority(row["severity"])

                validated_output = re.sub(
                    r"(Implementation Priority:\s*)(High|Medium|Low)",
                    r"\1" + true_priority,
                    llm_output
                )

                issue_category, engineering_solutions = extract_issue_and_solutions(validated_output)

                results.append({
                    "Row": idx + 1,
                    "Severity": row["severity"],
                    "Issue Category": issue_category,
                    "Engineering Solutions": engineering_solutions
                })

                progress.progress((idx - start + 2) / (end - start + 1))

            st.success("Analysis Complete")

            result_df = pd.DataFrame(results)

            st.dataframe(result_df)

            csv = result_df.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download Results",
                data=csv,
                file_name="analysis_results.csv",
                mime="text/csv"
            )


# ================================
# MANUAL MODE
# ================================

if mode == "Manual Input":

    user_input = st.text_area(
        "Enter Defect Description",
        height=200
    )

    if st.button("Analyze Issue"):

        extracted_text = extract_structured_fields_from_text(user_input)

        structured_data = parse_extracted_fields(extracted_text)

        issue_text = f"""
Defect Type: {structured_data['defect_type']}
Location: {structured_data['defect_location']}
Severity: {structured_data['severity']}
Inspection Method: {structured_data['inspection_method']}
Repair Cost: Unknown
"""

        prompt = build_prompt(issue_text)

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        llm_output = response.choices[0].message.content

        true_priority = assign_priority(structured_data["severity"])

        validated_output = re.sub(
            r"(Implementation Priority:\s*)(High|Medium|Low)",
            r"\1" + true_priority,
            llm_output
        )

        issue_category, engineering_solutions = extract_issue_and_solutions(validated_output)

        st.subheader("Issue Category")
        st.write(issue_category)

        st.subheader("Engineering Solutions")
        st.write(engineering_solutions)

        st.success("Processing Complete")