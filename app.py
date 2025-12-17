import streamlit as st
import pdfplumber
import edge_tts
import asyncio
import re
import os
import time
import random
from tenacity import retry, stop_after_attempt, wait_fixed

# Page Configuration
st.set_page_config(page_title="Prof. AI: Audio Classes", layout="wide")

st.title("👨‍🏫 Prof. AI: PDF to Audio Class")
st.write("I will read your questions, answers, and explanations in a detailed, teaching style.")

# --- Step 1: Upload File ---
uploaded_file = st.file_uploader("Upload your Q&A PDF", type="pdf")

def safe_clean_text(text):
    """
    Cleans text using a safe whitelist method.
    This removes special symbols without causing syntax errors.
    """
    if not text:
        return ""
    
    # 1. Replace newlines with spaces to keep sentences flowing
    text = text.replace("\n", " ")
    
    # 2. Remove specific markers found in your PDF
    # We use double quotes to avoid syntax errors
    text = text.replace("--- PAGE", "")
    text = text.replace("
    for char in text:
        if char in allowed_chars:
            clean_chars.append(char)
            
    # Join them back into a string
    cleaned_text = "".join(clean_chars)
    
    # 4. Remove extra spaces
    return " ".join(cleaned_text.split())

def extract_text_from_pdf(file):
    """Extracts raw text from PDF."""
    all_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"
    return all_text

def create_professor_script(label, main_text, explanation_text):
    """
    Creates a 'Professor' script.
    """
    # Intro
    script = f"Okay, let's move to {label}. "
    
    # Read Question and Answer
    script += f"The question is: {main_text}. "
    
    # Explanation
    if explanation_text:
        script += f" Now, let me explain the details. {explanation_text} "
        script += " So, that is the main point to remember here. "
    else:
        script += " That covers the answer for this one. "
        
    return script

def parse_pdf_to_lessons(text):
    """
    Splits text into Q&A blocks.
    Handles 'Q1.', '1.' and other numbering formats.
    """
    # Regex to split by "Q" + number OR just number + dot
    # Matches: "Q1.", "1.", "10."
    pattern = r"(?=\b(?:Q)?\d+\.\s)"
    chunks = re.split(pattern, text)
    
    lessons = []
    
    for chunk in chunks:
        clean_chunk = chunk.strip()
        
        # Skip empty or junk chunks
        if len(clean_chunk) < 5:
            continue
            
        # Find the label (e.g., "1" or "Q1")
        match = re.search(r"((?:Q)?\d+)", clean_chunk)
        label = match.group(1) if match else "Question"
        
        # Split into Answer and Explanation
        if "Explanation:" in clean_chunk:
            parts = clean_chunk.split("Explanation:")
            q_and_a = parts[0]
            explanation = parts[1]
        elif "Answer:" in clean_chunk:
            parts = clean_chunk.split("Answer:")
            q_and_a = parts[0] + " The answer is " + parts[1]
            explanation = ""
        else:
            q_and_a = clean_chunk
            explanation = ""

        # Clean the text
        final_main = safe_clean_text(q_and_a)
        final_exp = safe_clean_text(explanation)
        
        # Build Script
        audio_script = create_professor_script(label, final_main, final_exp)
        
        lessons.append({
            "label": label,
            "script": audio_script
        })
        
    return lessons

# --- Audio Generation with Retry ---
# Handles the '429 Too Many Requests' error automatically
@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def generate_audio(text, filename):
    # 'en-US-ChristopherNeural' is a deep, calm male voice (Professor style)
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- Main App ---
if uploaded_file is not None:
    with st.spinner("Processing PDF..."):
        raw_text = extract_text_from_pdf(uploaded_file)
        lessons = parse_pdf_to_lessons(raw_text)
    
    st.success(f"Found {len(lessons)} questions.")
    
    if st.button("Start Class (Generate Audio)"):
        
        progress_bar = st.progress(0)
        status_box = st.empty()
        
        for i, lesson in enumerate(lessons):
            label = lesson["label"]
            
            # Update Progress
            progress = (i + 1) / len(lessons)
            progress_bar.progress(progress)
            status_box.text(f"Professor is reading {label}...")
            
            with st.container():
                st.subheader(f"🎓 {label}")
                
                # Show Text (Optional)
                with st.expander("Show Transcript"):
                    st.write(lesson["script"])
                
                filename = f"audio_{i}.mp3"
                
                try:
                    # Generate Audio
                    asyncio.run(generate_audio(lesson["script"], filename))
                    
                    # Play Audio
                    with open(filename, "rb") as f:
                        audio_bytes = f.read()
                        st.audio(audio_bytes, format="audio/mp3")
                    
                    # Cleanup
                    os.remove(filename)
                    
                    # Sleep to prevent server blocking (Important!)
                    time.sleep(2.0)
                    
                except Exception as e:
                    st.error(f"Error on {label}: {e}")
            
            st.divider()
            
        status_box.text("Class Complete!")
        st.balloons()
