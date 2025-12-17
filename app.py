import streamlit as st
import pdfplumber
import edge_tts
import asyncio
import re
import os
import time
import random
from tenacity import retry, stop_after_attempt, wait_fixed

# Page Config
st.set_page_config(page_title="Prof. AI: Audio Classes", layout="wide")

st.title("👨‍🏫 Prof. AI: PDF to Audio Class")
st.write("I will read your PDF questions, answers, and explanations in a detailed, teaching style.")

# --- Step 1: Upload File ---
uploaded_file = st.file_uploader("Upload your Q&A PDF", type="pdf")

def clean_text(text):
    """Cleans text to ensure smooth speaking."""
    # 1. Remove citations like or [12]
    text = re.sub(r'\', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    
    # 2. Remove markers like '--- PAGE 1 ---'
    text = re.sub(r'--- PAGE \d+ ---', '', text)
    
    # 3. Remove special chars but keep punctuation
    # We use double quotes r"..." to avoid syntax errors with single quotes
    text = re.sub(r"[^a-zA-Z0-9\s.,?!:;'\-]", "", text)
    
    # 4. Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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
    Wraps the raw text in a 'Professor' persona script.
    """
    # 1. Intro
    script = f"Okay, let's look at {label}. "
    
    # 2. The Question (Assumes question is at the start)
    script += f"The question asks: {main_text}. "
    
    # 3. Transition to Explanation
    if explanation_text:
        script += f" Now, let's understand the details behind this. {explanation_text} "
        script += " So, that is the core concept here. "
    else:
        script += " That is the complete answer for this one. "
        
    return script

def parse_pdf_to_lessons(text):
    """
    Splits text into Q&A blocks and separates the 'Explanation' part.
    """
    # Split text by "Q" followed by digits (e.g. Q40., Q41.)
    # We use regex lookahead to keep the delimiter
    chunks = re.split(r'(?=Q\d+\.)', text)
    
    lessons = []
    
    for chunk in chunks:
        # Filter out junk text that doesn't start with Q
        if not chunk.strip().startswith("Q"):
            continue
            
        # Extract Question Number (Label)
        q_match = re.search(r'(Q\d+)', chunk)
        label = q_match.group(1) if q_match else "Question"
        
        # Split into Answer and Explanation parts if "Explanation:" exists
        if "Explanation:" in chunk:
            parts = chunk.split("Explanation:")
            q_and_a_part = parts[0]
            explanation_part = parts[1]
        elif "Answer:" in chunk:
             parts = chunk.split("Answer:")
             q_and_a_part = parts[0] + " The answer is: " + parts[1]
             explanation_part = ""
        else:
            q_and_a_part = chunk
            explanation_part = ""

        # Clean texts
        clean_main = clean_text(q_and_a_part)
        clean_exp = clean_text(explanation_part)
        
        # Create the audio script
        audio_script = create_professor_script(label, clean_main, clean_exp)
        
        lessons.append({
            "label": label,
            "display": chunk,
            "script": audio_script
        })
        
    return lessons

# --- Rate Limit Handling ---
# This decorator tries 3 times. If it fails, it waits 5 seconds and tries again.
@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def generate_safe_audio(text, filename):
    """
    Generates audio with retry logic to handle 429 errors.
    """
    # Male voice (Professor style): en-US-ChristopherNeural
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- Main App Logic ---
if uploaded_file is not None:
    with st.spinner("Analyzing PDF content..."):
        raw_text = extract_text_from_pdf(uploaded_file)
        lessons = parse_pdf_to_lessons(raw_text)
    
    st.success(f"Prepared {len(lessons)} detailed lessons.")
    st.info("Note: Generating audio takes a few seconds per question to ensure high quality and prevent server errors.")
    
    if st.button("Start Class (Generate Audio)"):
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, lesson in enumerate(lessons):
            label = lesson["label"]
            
            # Update Status
            progress = (i + 1) / len(lessons)
            progress_bar.progress(progress)
            status_text.text(f"Professor is explaining {label}...")
            
            # Create container
            with st.container():
                st.subheader(f"🎓 {label}")
                
                # Show text (optional)
                with st.expander("Read Transcript"):
                    st.write(lesson["script"])
                
                filename = f"lecture_{i}.mp3"
                
                try:
                    # 1. Generate Audio with Retries
                    asyncio.run(generate_safe_audio(lesson["script"], filename))
                    
                    # 2. Display Audio
                    with open(filename, 'rb') as f:
                        audio_bytes = f.read()
                        st.audio(audio_bytes, format='audio/mp3')
                    
                    # 3. Cleanup file
                    os.remove(filename)
                    
                    # 4. CRITICAL DELAY to prevent 429 Error
                    # Wait between 1.5 to 3 seconds randomly
                    time.sleep(random.uniform(1.5, 3.0))
                    
                except Exception as e:
                    st.error(f"Error on {label}: {e}")
            
            st.divider()
            
        status_text.text("Class Dismissed! All audio generated.")
        st.balloons()
