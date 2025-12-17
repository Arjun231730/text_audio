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
    Cleans text using a whitelist approach.
    This avoids Regex SyntaxErrors completely.
    """
    if not text:
        return ""
        
    # 1. Remove specific unwanted phrases using simple replace
    # (No regex involved here, just finding and deleting strings)
    text = text.replace(")
    
    # 3. Remove extra spaces
    cleaned_text = " ".join(cleaned_text.split())
    
    return cleaned_text

def extract_text_from_pdf(file):
    """Extracts raw text from PDF using pdfplumber."""
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
    # Intro
    script = f"Okay, let's look at {label}. "
    
    # Question and Answer
    # We add a clear pause after the main text
    script += f"The question asks: {main_text}. "
    
    # Transition to Explanation
    if explanation_text:
        script += f" Now, let's understand the details behind this. {explanation_text} "
        script += " So, that is the core concept here. "
    else:
        script += " That covers the complete answer for this question. "
        
    return script

def parse_pdf_to_lessons(text):
    """
    Splits text into Q&A blocks and separates the 'Explanation' part.
    """
    # Split text by "Q" followed by digits (e.g. Q40., Q41.)
    # We use a very simple regex here that is safe from syntax errors.
    chunks = re.split(r'(?=Q\d+\.)', text)
    
    lessons = []
    
    for chunk in chunks:
        clean_chunk = chunk.strip()
        
        # Only process chunks that actually start with "Q" followed by a number
        if not re.match(r'Q\d+', clean_chunk):
            continue
            
        # Extract Question Number (Label)
        # Finds "Q1", "Q40", etc.
        q_match = re.search(r'(Q\d+)', clean_chunk)
        label = q_match.group(1) if q_match else "Question"
        
        # Split into Answer and Explanation parts
        if "Explanation:" in clean_chunk:
            parts = clean_chunk.split("Explanation:")
            q_and_a_part = parts[0]
            explanation_part = parts[1]
        elif "Answer:" in clean_chunk:
             parts = clean_chunk.split("Answer:")
             q_and_a_part = parts[0] + " The answer is: " + parts[1]
             explanation_part = ""
        else:
            q_and_a_part = clean_chunk
            explanation_part = ""

        # Clean the text using our new whitelist function
        clean_main = safe_clean_text(q_and_a_part)
        clean_exp = safe_clean_text(explanation_part)
        
        # Create the audio script (Professor Style)
        audio_script = create_professor_script(label, clean_main, clean_exp)
        
        lessons.append({
            "label": label,
            "display": clean_chunk,
            "script": audio_script
        })
        
    return lessons

# --- Rate Limit Handling ---
# Retries up to 3 times if the server is busy (429 Error)
@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def generate_safe_audio(text, filename):
    """
    Generates audio using Edge TTS (Microsoft Neural Voice).
    """
    # Voice: 'en-US-ChristopherNeural' (Male, Professor-like)
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- Main App Logic ---
if uploaded_file is not None:
    with st.spinner("Analyzing PDF and preparing lectures..."):
        raw_text = extract_text_from_pdf(uploaded_file)
        lessons = parse_pdf_to_lessons(raw_text)
    
    st.success(f"Prepared {len(lessons)} detailed lessons.")
    st.info("Note: Generating high-quality audio takes about 2-3 seconds per question.")
    
    if st.button("Start Class (Generate Audio)"):
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, lesson in enumerate(lessons):
            label = lesson["label"]
            
            # Update Status
            progress = (i + 1) / len(lessons)
            progress_bar.progress(progress)
            status_text.text(f"Professor is explaining {label}...")
            
            # Create a visual container for each question
            with st.container():
                st.subheader(f"🎓 {label}")
                
                # Show the script text (optional, click to see)
                with st.expander("Read Transcript"):
                    st.write(lesson["script"])
                
                filename = f"lecture_{i}.mp3"
                
                try:
                    # 1. Generate Audio (Async run)
                    asyncio.run(generate_safe_audio(lesson["script"], filename))
                    
                    # 2. Display Audio Player
                    with open(filename, 'rb') as f:
                        audio_bytes = f.read()
                        st.audio(audio_bytes, format='audio/mp3')
                    
                    # 3. Cleanup: remove the temp file
                    os.remove(filename)
                    
                    # 4. SAFETY DELAY: Wait 2 seconds to avoid "Too Many Requests" error
                    time.sleep(2.0)
                    
                except Exception as e:
                    st.error(f"Error processing {label}: {e}")
            
            st.divider()
            
        status_text.text("Class Dismissed! All audio generated successfully.")
        st.balloons()
