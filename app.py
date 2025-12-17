import streamlit as st
import pdfplumber
from gtts import gTTS
import io
import re

# Page Config
st.set_page_config(page_title="PDF to Audio Converter", layout="wide")

st.title("📚 PDF Q&A to Audio Converter")
st.write("Upload your PDF (Format: Q1. ... Answer: ...). The app will separate them and create audio for each.")

# --- Step 1: Upload File ---
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

def extract_text_from_pdf(file):
    """Extracts all text from the uploaded PDF using pdfplumber for accuracy."""
    all_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"
    return all_text

def parse_questions(text):
    """
    Splits text into chunks based on 'Q' followed by a number (e.g., Q1., Q2.).
    It looks for the pattern: Q + digits + dot
    """
    # This regex looks for 'Q' followed by numbers and a dot (e.g., Q1., Q37.)
    # The '(?=...)' is a lookahead to split *before* the pattern without removing it.
    pattern = r'(?=Q\d+\.)'
    
    # Split text
    chunks = re.split(pattern, text)
    
    # Filter out any empty chunks (often the first one is empty header text)
    questions = [chunk.strip() for chunk in chunks if chunk.strip().startswith("Q")]
    return questions

def text_to_audio(text):
    """Converts text to an in-memory audio file using gTTS."""
    tts = gTTS(text=text, lang='en')
    audio_fp = io.BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0)
    return audio_fp

# --- Step 2: Process File ---
if uploaded_file is not None:
    with st.spinner("Extracting text from PDF..."):
        raw_text = extract_text_from_pdf(uploaded_file)
    
    # Show extracted text (optional, for verification)
    with st.expander("View Extracted Text"):
        st.text(raw_text)

    # Split into Q&A
    qa_list = parse_questions(raw_text)
    
    st.success(f"Found {len(qa_list)} Questions!")
    st.divider()

    # --- Step 3: Generate & Display Audio ---
    if st.button("Generate Audio for All Questions"):
        progress_bar = st.progress(0)
        
        for i, qa_text in enumerate(qa_list):
            # Update progress
            progress = (i + 1) / len(qa_list)
            progress_bar.progress(progress)
            
            # Extract the Question Number for the label (e.g., "Q1")
            label = qa_text.split('.')[0] 
            
            # Create a container for each question
            with st.container():
                st.subheader(f"{label}")
                
                # Show the text being read
                with st.expander(f"Read Text for {label}"):
                    st.write(qa_text)

                # Generate Audio
                try:
                    # We use a spinner for each item because gTTS relies on internet API
                    audio_bytes = text_to_audio(qa_text)
                    st.audio(audio_bytes, format='audio/mp3')
                except Exception as e:
                    st.error(f"Error converting audio for {label}: {e}")
                
                st.divider()
        
        st.success("All audio files generated successfully!")